"""The dashboard: each pet's summary, what needs doing, and what is next.

The thing worth breaking the build over is the ranking. "Urgent" has to mean
one thing, and it has to mean an animal may need seeing or an appointment may
be lost - not "a vaccination is due next month". A dashboard where everything
shouts is one nobody reads, and the cost of that is the red triage result
scrolling past unnoticed.
"""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers every table with Base.metadata
from app.db.base import Base
from app.models import (
    AgeCategory,
    Animal,
    AvailabilitySlot,  # noqa: F401 - keeps the appointment FK resolvable
    Recurrence,
    Reminder,
    ReminderOccurrence,
    ReminderType,
    User,
    UserRole,
)
from app.models.appointment import Appointment, AppointmentMessage, AppointmentStatus
from app.models.symptom_check import SymptomCheck
from app.services.dashboard import build_dashboard

TODAY = date.today()


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def owner(session):
    user = User(email="owner@example.com", display_name="Owner")
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def vet(session):
    user = User(
        email="vet@example.com",
        display_name="Dr. Vet",
        role=UserRole.VETERINARIAN,
        clinic_name="Riverside Veterinary Clinic",
        accepts_appointments=True,
    )
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def buddy(session, owner):
    animal = Animal(
        name="Buddy", species="dog", age_category=AgeCategory.ADULT, owner_id=owner.id
    )
    session.add(animal)
    session.commit()
    return animal


def add_reminder(session, owner, animal, *, due, title="Worming tablet", recurrence=Recurrence.NONE):
    reminder = Reminder(
        title=title,
        reminder_type=ReminderType.OTHER,
        due_date=due,
        recurrence=recurrence,
        owner_id=owner.id,
        animal_id=animal.id,
    )
    session.add(reminder)
    session.commit()
    return reminder


def add_appointment(session, owner, vet, animal, **fields):
    defaults = dict(
        owner_id=owner.id,
        vet_id=vet.id,
        animal_id=animal.id if animal else None,
        reason="Limping.",
        preferred_date=TODAY,
    )
    defaults.update(fields)
    appointment = Appointment(**defaults)
    session.add(appointment)
    session.commit()
    return appointment


def add_check(session, owner, animal, level, *, days_ago=0, headline="See a vet today"):
    check = SymptomCheck(
        user_id=owner.id,
        animal_id=animal.id,
        intake={},
        triage={"headline": headline, "level": level},
        triage_level=level,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    session.add(check)
    session.commit()
    return check


def kinds(data) -> list[str]:
    return [task.kind for task in data["tasks"]]


# ------------------------------------------------------------ per-pet summary


def test_a_new_account_with_no_pets_has_nothing_to_show(session, owner):
    data = build_dashboard(session, owner, today=TODAY)

    assert data["pets"] == []
    assert data["tasks"] == []
    assert data["next_appointment"] is None
    assert data["urgent_count"] == 0


def test_each_pet_gets_its_own_summary(session, owner, buddy):
    milo = Animal(
        name="Milo", species="cat", age_category=AgeCategory.ADULT, owner_id=owner.id
    )
    session.add(milo)
    session.commit()

    data = build_dashboard(session, owner, today=TODAY)

    assert [summary.animal.name for summary in data["pets"]] == ["Buddy", "Milo"]


def test_the_summary_carries_the_next_thing_due(session, owner, buddy):
    add_reminder(session, owner, buddy, due=TODAY + timedelta(days=10), title="Booster")
    add_reminder(session, owner, buddy, due=TODAY + timedelta(days=3), title="Flea drops")

    summary = build_dashboard(session, owner, today=TODAY)["pets"][0]

    assert summary.next_reminder_title == "Flea drops"
    assert summary.next_reminder_date == TODAY + timedelta(days=3)


def test_a_reminder_already_ticked_off_stops_counting_as_overdue(session, owner, buddy):
    """The whole reason marking things done exists. A dose done last week must
    not keep the pet showing red on the dashboard."""
    reminder = add_reminder(session, owner, buddy, due=TODAY - timedelta(days=5))

    before = build_dashboard(session, owner, today=TODAY)["pets"][0]
    assert before.overdue_reminders == 1

    session.add(
        ReminderOccurrence(
            reminder_id=reminder.id,
            occurrence_date=TODAY - timedelta(days=5),
            completed_at=datetime.now(timezone.utc),
        )
    )
    session.commit()

    after = build_dashboard(session, owner, today=TODAY)["pets"][0]
    assert after.overdue_reminders == 0
    assert "overdue_reminder" not in kinds(build_dashboard(session, owner, today=TODAY))


def test_the_latest_symptom_check_lands_on_the_pet(session, owner, buddy):
    add_check(session, owner, buddy, "green", days_ago=9, headline="Watch at home")
    add_check(session, owner, buddy, "amber", days_ago=1, headline="See a vet soon")

    summary = build_dashboard(session, owner, today=TODAY)["pets"][0]

    # Only the newest. A pet checked three times last week has one current
    # answer, and listing all three would bury it.
    assert summary.last_check_level == "amber"
    assert summary.last_check_headline == "See a vet soon"


# -------------------------------------------------------------------- ranking


def test_a_red_triage_outranks_everything_else(session, owner, vet, buddy):
    """The only thing on this page that can mean an animal needs seeing today."""
    add_reminder(session, owner, buddy, due=TODAY - timedelta(days=20), title="Booster")
    add_appointment(
        session,
        owner,
        vet,
        buddy,
        status=AppointmentStatus.CONFIRMED,
        scheduled_date=TODAY,
        scheduled_time=time(10, 0),
    )
    add_check(session, owner, buddy, "red")

    data = build_dashboard(session, owner, today=TODAY)

    assert kinds(data)[0] == "triage"
    assert data["tasks"][0].severity == "urgent"
    assert data["urgent_count"] == 1


def test_an_old_red_result_stops_being_a_task(session, owner, buddy):
    """A red result from March is not an urgent task in August - either the
    animal was seen or it resolved, and nagging teaches people to ignore the
    panel. It stays on the pet's summary as history."""
    add_check(session, owner, buddy, "red", days_ago=40)

    data = build_dashboard(session, owner, today=TODAY)

    assert "triage" not in kinds(data)
    assert data["pets"][0].last_check_level == "red"


def test_a_green_check_is_never_a_task(session, owner, buddy):
    add_check(session, owner, buddy, "green", headline="Home care is reasonable")

    assert "triage" not in kinds(build_dashboard(session, owner, today=TODAY))


def test_a_suggested_move_waiting_on_the_owner_is_urgent(session, owner, vet, buddy):
    """Until they answer, the appointment they think they have may not happen."""
    add_appointment(
        session,
        owner,
        vet,
        buddy,
        status=AppointmentStatus.RESCHEDULE_PROPOSED,
        scheduled_date=TODAY + timedelta(days=5),
        scheduled_time=time(9, 0),
        proposed_date=TODAY + timedelta(days=8),
        proposed_time=time(14, 30),
        proposed_by_id=vet.id,
    )

    data = build_dashboard(session, owner, today=TODAY)

    waiting = [task for task in data["tasks"] if task.kind == "reschedule_waiting"]
    assert len(waiting) == 1 and waiting[0].severity == "urgent"


def test_a_move_the_owner_suggested_is_not_their_task(session, owner, vet, buddy):
    """It is waiting on the practice. Listing it here would be telling somebody
    to answer their own question."""
    add_appointment(
        session,
        owner,
        vet,
        buddy,
        status=AppointmentStatus.RESCHEDULE_PROPOSED,
        scheduled_date=TODAY + timedelta(days=5),
        proposed_date=TODAY + timedelta(days=8),
        proposed_by_id=owner.id,
    )

    assert "reschedule_waiting" not in kinds(build_dashboard(session, owner, today=TODAY))


def test_overdue_care_ranks_above_something_merely_scheduled(session, owner, vet, buddy):
    add_reminder(session, owner, buddy, due=TODAY - timedelta(days=3), title="Worming")
    appointment = add_appointment(
        session,
        owner,
        vet,
        buddy,
        status=AppointmentStatus.CONFIRMED,
        scheduled_date=TODAY + timedelta(days=1),
        scheduled_time=time(11, 0),
    )
    session.add(
        AppointmentMessage(
            appointment_id=appointment.id, sender_id=vet.id, body="Bring his notes."
        )
    )
    session.commit()

    order = kinds(build_dashboard(session, owner, today=TODAY))

    # Both deadlines first, the message last: unread post is worth knowing and
    # nothing more.
    assert order.index("overdue_reminder") < order.index("unread_messages")
    assert order.index("appointment_soon") < order.index("unread_messages")


def test_an_unread_message_from_the_owner_themselves_is_not_unread(session, owner, vet, buddy):
    appointment = add_appointment(session, owner, vet, buddy)
    session.add(
        AppointmentMessage(
            appointment_id=appointment.id, sender_id=owner.id, body="Any update?"
        )
    )
    session.commit()

    assert "unread_messages" not in kinds(build_dashboard(session, owner, today=TODAY))


def test_an_appointment_far_off_is_not_a_task_but_is_still_next(session, owner, vet, buddy):
    """"You have an appointment" is not something to do about an appointment in
    three weeks. It still belongs on the card."""
    add_appointment(
        session,
        owner,
        vet,
        buddy,
        status=AppointmentStatus.CONFIRMED,
        scheduled_date=TODAY + timedelta(days=21),
        scheduled_time=time(9, 30),
    )

    data = build_dashboard(session, owner, today=TODAY)

    assert "appointment_soon" not in kinds(data)
    assert data["next_appointment"] is not None
    assert data["pets"][0].next_appointment is not None


# --------------------------------------------------------- next appointment


def test_the_next_appointment_is_the_soonest_confirmed_one(session, owner, vet, buddy):
    add_appointment(
        session,
        owner,
        vet,
        buddy,
        status=AppointmentStatus.CONFIRMED,
        scheduled_date=TODAY + timedelta(days=10),
        scheduled_time=time(9, 0),
    )
    sooner = add_appointment(
        session,
        owner,
        vet,
        buddy,
        status=AppointmentStatus.CONFIRMED,
        scheduled_date=TODAY + timedelta(days=4),
        scheduled_time=time(15, 0),
    )

    assert build_dashboard(session, owner, today=TODAY)["next_appointment"].id == sooner.id


def test_a_declined_or_cancelled_appointment_is_not_next(session, owner, vet, buddy):
    for status in (AppointmentStatus.DECLINED, AppointmentStatus.CANCELLED,
                   AppointmentStatus.REQUESTED):
        add_appointment(
            session,
            owner,
            vet,
            buddy,
            status=status,
            scheduled_date=TODAY + timedelta(days=2),
        )

    assert build_dashboard(session, owner, today=TODAY)["next_appointment"] is None


def test_a_past_appointment_is_not_next(session, owner, vet, buddy):
    add_appointment(
        session,
        owner,
        vet,
        buddy,
        status=AppointmentStatus.CONFIRMED,
        scheduled_date=TODAY - timedelta(days=1),
        scheduled_time=time(9, 0),
    )

    assert build_dashboard(session, owner, today=TODAY)["next_appointment"] is None


def test_an_appointment_with_no_pet_still_counts_as_your_next_visit(session, owner, vet):
    """Somebody asking "when am I next at the vet" does not care which record
    it hangs off."""
    add_appointment(
        session,
        owner,
        vet,
        None,
        status=AppointmentStatus.CONFIRMED,
        scheduled_date=TODAY + timedelta(days=3),
        scheduled_time=time(10, 0),
    )

    assert build_dashboard(session, owner, today=TODAY)["next_appointment"] is not None


# ------------------------------------------------------------------ isolation


def test_another_owners_pets_and_tasks_never_appear(session, owner, vet, buddy):
    stranger = User(email="nosy@example.com", display_name="Nosy")
    session.add(stranger)
    session.commit()
    theirs = Animal(
        name="Rex", species="dog", age_category=AgeCategory.ADULT, owner_id=stranger.id
    )
    session.add(theirs)
    session.commit()
    add_reminder(session, stranger, theirs, due=TODAY - timedelta(days=5))
    add_check(session, stranger, theirs, "red")

    data = build_dashboard(session, owner, today=TODAY)

    assert [summary.animal.name for summary in data["pets"]] == ["Buddy"]
    assert data["tasks"] == []


def test_a_pets_own_task_list_holds_only_its_own(session, owner, vet, buddy):
    milo = Animal(
        name="Milo", species="cat", age_category=AgeCategory.ADULT, owner_id=owner.id
    )
    session.add(milo)
    session.commit()
    add_reminder(session, owner, buddy, due=TODAY - timedelta(days=2), title="Buddy's worming")
    add_check(session, owner, milo, "red", headline="See a vet today")

    data = build_dashboard(session, owner, today=TODAY)
    by_name = {summary.animal.name: summary for summary in data["pets"]}

    assert kinds(data) == ["triage", "overdue_reminder"]
    assert [task.kind for task in by_name["Buddy"].tasks] == ["overdue_reminder"]
    assert [task.kind for task in by_name["Milo"].tasks] == ["triage"]
