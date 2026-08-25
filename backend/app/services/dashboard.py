"""Everything the dashboard shows, assembled in one place.

Built server-side and served as one response, for two reasons.

The first is that the page was already over budget. A browser opens six
connections per origin over HTTP/1.1, and this dashboard was firing the session
check, the notification count, the reminders list, the community feed and the
getting-started checks on mount - the last of which had already been made
sequential because the queue was costing the community panel its request
entirely. Adding per-pet summaries, tasks and appointments as four more calls
would have made that worse for everybody.

The second is that "urgent" is a judgement, and it has to be made once. The
same overdue reminder must not read as urgent on this page and routine on the
calendar; a triage result that said "see a vet today" must outrank a vaccination
due next week whichever screen you are looking at. Ranking on the client would
put that judgement in whichever component happened to render first.

Nothing here is stored. Every number is true at the moment it is asked for, and
a cached "2 overdue" is wrong the second somebody ticks one off.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import AIAnalysisLog, Animal, Reminder, User
from app.models.appointment import Appointment, AppointmentStatus
from app.models.symptom_check import SymptomCheck
from app.services.profile_match import find_conflicts
from app.services.recurrence import next_pending_occurrence

Severity = Literal["urgent", "soon", "info"]

#: Sort fallback for an appointment confirmed before exact times existed.
_MIDNIGHT = time(0, 0)

#: How long a symptom check stays worth surfacing on the dashboard.
#:
#: A red result from March is not an urgent task in August - either the animal
#: was seen or the problem resolved, and either way the dashboard nagging about
#: it teaches somebody to ignore the panel. Two weeks is long enough that a
#: check made last weekend is still on the page, and short enough that the list
#: empties on its own.
TRIAGE_TASK_WINDOW_DAYS = 14

#: A confirmed appointment inside this many days is worth saying out loud.
APPOINTMENT_SOON_DAYS = 2


@dataclass
class Task:
    """One thing worth doing, with a reason and somewhere to go.

    `severity` is about consequence, not loudness. "urgent" means an animal may
    need seeing or an appointment may be lost; "soon" means it has a deadline;
    "info" is worth knowing and nothing more. Nothing on this list is styled
    red unless it earns it, because a dashboard where everything shouts is a
    dashboard nobody reads.
    """

    kind: str
    severity: Severity
    title: str
    detail: str
    link: str
    pet_name: str | None = None
    #: Sort key within a severity band. Lower is sooner.
    due: date | None = None


@dataclass
class PetSummary:
    animal: Animal
    overdue_reminders: int = 0
    next_reminder_title: str | None = None
    next_reminder_date: date | None = None
    next_appointment: Appointment | None = None
    last_check_level: str | None = None
    last_check_headline: str | None = None
    last_check_at: date | None = None
    last_analysis_at: date | None = None
    #: Serious disagreements between the newest analysis and this profile.
    profile_conflicts: int = 0
    tasks: list[Task] = field(default_factory=list)


_SEVERITY_ORDER = {"urgent": 0, "soon": 1, "info": 2}


def _rank(task: Task) -> tuple:
    return (_SEVERITY_ORDER[task.severity], task.due or date.max, task.title)


def build_dashboard(db: Session, user: User, *, today: date | None = None) -> dict[str, Any]:
    """The whole page, for one person, right now."""
    today = today or date.today()

    animals = list(
        db.scalars(
            select(Animal).where(Animal.owner_id == user.id).order_by(Animal.name)
        ).all()
    )
    by_animal = {animal.id: PetSummary(animal=animal) for animal in animals}

    reminders = list(
        db.scalars(
            select(Reminder)
            .options(selectinload(Reminder.occurrences), joinedload(Reminder.animal))
            .where(Reminder.owner_id == user.id)
        )
        .unique()
        .all()
    )
    appointments = list(
        db.scalars(
            select(Appointment)
            .options(
                joinedload(Appointment.vet),
                joinedload(Appointment.animal),
                selectinload(Appointment.messages),
            )
            .where(Appointment.owner_id == user.id)
        )
        .unique()
        .all()
    )
    checks = list(
        db.scalars(
            select(SymptomCheck)
            .where(SymptomCheck.user_id == user.id)
            .order_by(SymptomCheck.created_at.desc())
        ).all()
    )
    analyses = list(
        db.scalars(
            select(AIAnalysisLog)
            .options(joinedload(AIAnalysisLog.animal))
            .where(AIAnalysisLog.user_id == user.id)
            .order_by(AIAnalysisLog.created_at.desc())
        )
        .unique()
        .all()
    )

    tasks: list[Task] = []
    _fold_reminders(reminders, by_animal, tasks, today)
    _fold_appointments(appointments, by_animal, tasks, today, user)
    _fold_checks(checks, by_animal, tasks, today)
    _fold_analyses(analyses, by_animal, tasks, today)

    tasks.sort(key=_rank)
    for summary in by_animal.values():
        summary.tasks.sort(key=_rank)

    # The soonest confirmed visit across every pet, including the ones with no
    # pet attached - an owner asking "when am I next at the vet" does not care
    # which record it hangs off.
    upcoming = [
        appointment
        for appointment in appointments
        if appointment.status
        in (AppointmentStatus.CONFIRMED, AppointmentStatus.RESCHEDULE_PROPOSED)
        and appointment.scheduled_date
        and appointment.scheduled_date >= today
    ]
    upcoming.sort(key=lambda item: (item.scheduled_date, item.scheduled_time or _MIDNIGHT))

    return {
        "pets": [by_animal[animal.id] for animal in animals],
        "tasks": tasks,
        "next_appointment": upcoming[0] if upcoming else None,
        "urgent_count": sum(1 for task in tasks if task.severity == "urgent"),
    }


def _fold_reminders(
    reminders: list[Reminder],
    by_animal: dict,
    tasks: list[Task],
    today: date,
) -> None:
    """Overdue counts and the next thing due, per pet.

    Two questions, and they need two different searches. "What is still
    outstanding" has to look BACKWARDS from the reminder's own start date - a
    one-off that was due last Tuesday has no occurrence on or after today at
    all, so asking "what is next from today" reports it as nothing rather than
    as overdue, which is exactly the reminder somebody most needs to see.
    "What is coming up" looks forward from today as you would expect.

    Both skip occurrences already ticked off, so a dose done last week does not
    keep the pet showing red - which is the whole reason marking things done
    exists.
    """
    for reminder in reminders:
        summary = by_animal.get(reminder.animal_id)
        if summary is None:
            continue

        # From the reminder's own due date rather than an arbitrary window: an
        # overdue booster from two years ago is still overdue, and any cut-off
        # would quietly stop counting it.
        earliest = next_pending_occurrence(reminder, reminder.due_date)
        upcoming = next_pending_occurrence(reminder, today)

        if earliest is not None and earliest.date < today:
            summary.overdue_reminders += 1
            days = (today - earliest.date).days
            task = Task(
                kind="overdue_reminder",
                # Overdue care has a real cost and no deadline left to meet, so
                # it outranks anything merely scheduled. It is not "urgent" in
                # the see-a-vet-now sense, which is reserved for triage.
                severity="soon",
                title=f"{reminder.title} is overdue",
                detail=(
                    f"{summary.animal.name} - due {earliest.date:%d %b}, "
                    f"{days} day{'s' if days != 1 else ''} ago."
                ),
                link="/calendar",
                pet_name=summary.animal.name,
                due=earliest.date,
            )
            tasks.append(task)
            summary.tasks.append(task)

        # "Next due" is only ever something still to come. An overdue item is
        # reported as overdue; showing it here as well would have the card say
        # a date in the past under a heading that reads as future.
        if upcoming is not None and (
            summary.next_reminder_date is None or upcoming.date < summary.next_reminder_date
        ):
            summary.next_reminder_date = upcoming.date
            summary.next_reminder_title = reminder.title


def _fold_appointments(
    appointments: list[Appointment],
    by_animal: dict,
    tasks: list[Task],
    today: date,
    user: User,
) -> None:
    for appointment in appointments:
        summary = by_animal.get(appointment.animal_id)
        practice = appointment.vet.clinic_name or appointment.vet.display_name
        pet_name = appointment.animal.name if appointment.animal else None

        if (
            appointment.status
            in (AppointmentStatus.CONFIRMED, AppointmentStatus.RESCHEDULE_PROPOSED)
            and appointment.scheduled_date
            and appointment.scheduled_date >= today
        ):
            if summary is not None and (
                summary.next_appointment is None
                or appointment.scheduled_date < summary.next_appointment.scheduled_date
            ):
                summary.next_appointment = appointment

            days_away = (appointment.scheduled_date - today).days
            if days_away <= APPOINTMENT_SOON_DAYS:
                when = "today" if days_away == 0 else "tomorrow" if days_away == 1 else f"in {days_away} days"
                clock = (
                    f" at {appointment.scheduled_time:%H:%M}"
                    if appointment.scheduled_time
                    else ""
                )
                task = Task(
                    kind="appointment_soon",
                    severity="soon",
                    title=f"Appointment {when}{clock}",
                    detail=f"{practice}" + (f" - for {pet_name}" if pet_name else ""),
                    link="/appointments",
                    pet_name=pet_name,
                    due=appointment.scheduled_date,
                )
                tasks.append(task)
                if summary is not None:
                    summary.tasks.append(task)

        # A move suggested by the practice is waiting on this owner, and until
        # they answer it the appointment they think they have may not happen.
        if (
            appointment.status is AppointmentStatus.RESCHEDULE_PROPOSED
            and appointment.proposed_by_id != user.id
        ):
            task = Task(
                kind="reschedule_waiting",
                severity="urgent",
                title="A new appointment time needs your answer",
                detail=(
                    f"{practice} suggested "
                    f"{appointment.proposed_date:%d %b}"
                    + (
                        f" at {appointment.proposed_time:%H:%M}"
                        if appointment.proposed_time
                        else ""
                    )
                    + ". Nothing moves until you accept or decline."
                ),
                link="/appointments",
                pet_name=pet_name,
                due=appointment.proposed_date,
            )
            tasks.append(task)
            if summary is not None:
                summary.tasks.append(task)

        unread = sum(
            1
            for message in appointment.messages
            if message.sender_id != user.id and message.read_at is None
        )
        if unread:
            task = Task(
                kind="unread_messages",
                severity="info",
                title=f"{unread} unread message{'s' if unread != 1 else ''} from {practice}",
                detail="About your appointment.",
                link="/appointments",
                pet_name=pet_name,
            )
            tasks.append(task)
            if summary is not None:
                summary.tasks.append(task)


def _fold_checks(
    checks: list[SymptomCheck], by_animal: dict, tasks: list[Task], today: date
) -> None:
    """The newest symptom check per pet, and a task while it is still recent.

    Only the newest counts. A pet checked three times last week has one current
    answer, and listing all three would bury it.
    """
    seen: set = set()
    for check in checks:
        if check.animal_id is None or check.animal_id in seen:
            continue
        summary = by_animal.get(check.animal_id)
        if summary is None:
            continue
        seen.add(check.animal_id)

        when = check.created_at.date()
        summary.last_check_level = check.triage_level
        summary.last_check_at = when
        headline = (check.triage or {}).get("headline")
        summary.last_check_headline = headline if isinstance(headline, str) else None

        if (today - when).days > TRIAGE_TASK_WINDOW_DAYS:
            continue
        if check.triage_level not in ("red", "amber"):
            continue
        task = Task(
            kind="triage",
            # The only thing on this page that can mean an animal needs seeing
            # today. Everything else is scheduling.
            severity="urgent" if check.triage_level == "red" else "soon",
            title=(
                f"{summary.animal.name}: {summary.last_check_headline or 'symptom check needs following up'}"
            ),
            detail=f"From the symptom check on {when:%d %b}.",
            link="/symptom-check/history",
            pet_name=summary.animal.name,
            due=when,
        )
        tasks.append(task)
        summary.tasks.append(task)


def _fold_analyses(
    analyses: list[AIAnalysisLog], by_animal: dict, tasks: list[Task], today: date
) -> None:
    """The newest analysis per pet, and any serious contradiction it raises."""
    seen: set = set()
    for analysis in analyses:
        if analysis.animal_id is None or analysis.animal_id in seen:
            continue
        summary = by_animal.get(analysis.animal_id)
        if summary is None:
            continue
        seen.add(analysis.animal_id)
        summary.last_analysis_at = analysis.created_at.date()

        serious = [
            conflict
            for conflict in find_conflicts(
                analysis.animal, analysis.result, analysis.correction, today=today
            )
            if conflict.severity == "high"
        ]
        summary.profile_conflicts = len(serious)
        if not serious:
            continue
        task = Task(
            kind="profile_conflict",
            # Worth knowing, not worth alarm. Neither side is presumed right -
            # see profile_match - so this is an invitation to check, not a
            # report that something is wrong.
            severity="info",
            title=f"{summary.animal.name}'s latest analysis does not match their profile",
            detail=serious[0].message,
            link=f"/analysis/{analysis.id}",
            pet_name=summary.animal.name,
        )
        tasks.append(task)
        summary.tasks.append(task)
