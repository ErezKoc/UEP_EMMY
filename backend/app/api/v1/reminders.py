import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Animal, Reminder, ReminderOccurrence, User
from app.schemas.reminder import (
    DuplicateGroup,
    DuplicateResolution,
    OccurrenceSnooze,
    ReminderCreate,
    ReminderOccurrenceRead,
    ReminderRead,
    ReminderUpdate,
)
from app.services.recurrence import (
    describe,
    next_pending_occurrence,
    resolved_occurrences,
)

router = APIRouter()

#: The furthest ahead the occurrence endpoint will generate.
#:
#: A month view asks for six weeks. Without a ceiling, `?start=2020-01-01&
#: end=2400-01-01` on a daily reminder is 150,000 dates built in memory to
#: answer one request.
MAX_WINDOW_DAYS = 800


def _with_schedule(reminder: Reminder) -> ReminderRead:
    """The stored row plus the things only the server can work out.

    The calendar could once compute the next date itself; it no longer tries,
    because the answer now depends on which instances have been ticked off and
    which were pushed back. One implementation, on the side that also has to
    tell an email scheduler the same thing.
    """
    data = ReminderRead.model_validate(reminder)
    upcoming = next_pending_occurrence(reminder, date.today())
    data.next_occurrence = upcoming.date if upcoming else None
    data.next_scheduled_date = upcoming.scheduled_date if upcoming else None
    data.next_is_snoozed = bool(upcoming and upcoming.snoozed)
    data.recurrence_description = describe(reminder)
    done = sorted(
        (item.occurrence_date for item in reminder.occurrences if item.is_done)
    )
    data.completed_count = len(done)
    data.last_completed_date = done[-1] if done else None
    # Nothing left to do. Two ways to get there: a one-off that has been ticked
    # off, and a repeating one that has run past its end date. Both should stop
    # occupying the calendar, which is most of what "cluttered" meant.
    data.is_finished = upcoming is None
    return data


def _owned_animal(db: Session, animal_id: uuid.UUID, user: User) -> Animal:
    animal = db.get(Animal, animal_id)
    if animal is None or animal.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Pet not found.")
    return animal


def _owned_reminder(db: Session, reminder_id: uuid.UUID, user: User) -> Reminder:
    reminder = db.scalar(
        select(Reminder)
        .options(joinedload(Reminder.animal), selectinload(Reminder.occurrences))
        .where(Reminder.id == reminder_id)
    )
    if reminder is None or reminder.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Reminder not found.")
    return reminder


def _all_owned(db: Session, user: User) -> list[Reminder]:
    return list(
        db.scalars(
            select(Reminder)
            .options(joinedload(Reminder.animal), selectinload(Reminder.occurrences))
            .where(Reminder.owner_id == user.id)
            .order_by(Reminder.due_date, Reminder.created_at)
        )
        .unique()
        .all()
    )


def _duplicate_key(reminder: Reminder) -> tuple:
    """What makes two reminders the same reminder.

    Title compared case- and space-insensitively, because the copies people
    actually end up with are "Rabies vaccine" and "rabies  vaccine" typed a
    fortnight apart, not byte-identical strings. Notes are deliberately NOT
    part of the key: two entries for the same jab on the same day are the same
    jab whether or not somebody annotated one of them.
    """
    return (
        reminder.animal_id,
        reminder.reminder_type,
        reminder.due_date,
        " ".join(reminder.title.lower().split()),
    )


@router.get("", response_model=list[ReminderRead])
def list_reminders(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    animal_id: uuid.UUID | None = Query(default=None),
    include_finished: bool = Query(
        default=True,
        description="Set false to leave out reminders with nothing left to do.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReminderRead]:
    statement = (
        select(Reminder)
        .options(joinedload(Reminder.animal), selectinload(Reminder.occurrences))
        .where(Reminder.owner_id == current_user.id)
    )
    if start:
        statement = statement.where(Reminder.due_date >= start)
    if end:
        statement = statement.where(Reminder.due_date <= end)
    if animal_id:
        statement = statement.where(Reminder.animal_id == animal_id)
    reminders = (
        db.scalars(statement.order_by(Reminder.due_date, Reminder.created_at))
        .unique()
        .all()
    )
    rows = [_with_schedule(reminder) for reminder in reminders]
    if not include_finished:
        rows = [row for row in rows if not row.is_finished]
    return rows


@router.get("/occurrences", response_model=list[ReminderOccurrenceRead])
def list_occurrences(
    start: date = Query(...),
    end: date = Query(...),
    animal_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReminderOccurrenceRead]:
    """Every dated instance the calendar has to draw in this window.

    The month grid used to work these out in the browser from a mirrored copy
    of the recurrence rules. That was tolerable while the answer was pure
    arithmetic; it stopped being so the moment an instance could be ticked off
    or pushed back, because the mirror would have had to duplicate those too.
    One implementation now, and the grid draws what it is told.
    """
    if end < start:
        raise HTTPException(status_code=400, detail="The end date is before the start.")
    if (end - start).days > MAX_WINDOW_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Ask for at most {MAX_WINDOW_DAYS} days at a time.",
        )

    statement = (
        select(Reminder)
        .options(selectinload(Reminder.occurrences))
        .where(Reminder.owner_id == current_user.id)
    )
    if animal_id:
        statement = statement.where(Reminder.animal_id == animal_id)

    rows: list[ReminderOccurrenceRead] = []
    for reminder in db.scalars(statement).unique().all():
        for item in resolved_occurrences(reminder, start, end):
            rows.append(
                ReminderOccurrenceRead(
                    reminder_id=reminder.id,
                    scheduled_date=item.scheduled_date,
                    date=item.date,
                    done=item.done,
                    snoozed=item.snoozed,
                )
            )
    rows.sort(key=lambda item: (item.date, item.scheduled_date))
    return rows


@router.get("/duplicates", response_model=list[DuplicateGroup])
def list_duplicates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DuplicateGroup]:
    """Reminders that say exactly the same thing as another one.

    Reported rather than deleted. The obvious version of this feature quietly
    removes the extras, and the one time it is wrong somebody loses a reminder
    for a booster they will now miss - so it hands back the groups and lets a
    person look at them first.
    """
    groups: dict[tuple, list[Reminder]] = defaultdict(list)
    for reminder in _all_owned(db, current_user):
        groups[_duplicate_key(reminder)].append(reminder)

    found: list[DuplicateGroup] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        # Oldest first: it is the one carrying the history - its completions,
        # and whatever an appointment confirmation wrote into its notes.
        members.sort(key=lambda item: item.created_at)
        keeper, *copies = members
        found.append(
            DuplicateGroup(
                title=keeper.title,
                reminder_type=keeper.reminder_type,
                due_date=keeper.due_date,
                animal_id=keeper.animal_id,
                animal_name=keeper.animal.name if keeper.animal else "",
                keep_id=keeper.id,
                duplicate_ids=[copy.id for copy in copies],
                reminders=[_with_schedule(item) for item in members],
            )
        )
    found.sort(key=lambda group: (group.due_date, group.title))
    return found


@router.post("/duplicates/resolve", response_model=list[ReminderRead])
def resolve_duplicates(
    payload: DuplicateResolution,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReminderRead]:
    """Delete the named copies, and only ones that really are copies.

    Every id is re-checked against the live duplicate groups before anything is
    removed. A page open in another tab can be minutes stale, and "delete these
    ids" from a stale page must not be able to delete the last remaining copy
    of something after the others were already tidied up elsewhere.
    """
    removable: set[uuid.UUID] = set()
    for group in list_duplicates(db=db, current_user=current_user):
        removable.update(group.duplicate_ids)

    unknown = [item for item in payload.delete_ids if item not in removable]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Some of those are no longer duplicates - the list has changed "
                "since it was loaded. Reload and try again."
            ),
        )

    for reminder_id in set(payload.delete_ids):
        db.delete(_owned_reminder(db, reminder_id, current_user))
    db.commit()
    return [_with_schedule(reminder) for reminder in _all_owned(db, current_user)]


@router.post("", response_model=ReminderRead, status_code=status.HTTP_201_CREATED)
def create_reminder(
    payload: ReminderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReminderRead:
    _owned_animal(db, payload.animal_id, current_user)
    reminder = Reminder(**payload.model_dump(), owner_id=current_user.id)

    # Refused at the source, so the duplicate list stays a way of clearing up
    # history rather than a bucket that refills every week. 409 with the id of
    # the one that already exists, so the interface can point at it instead of
    # only saying no.
    existing = next(
        (
            item
            for item in _all_owned(db, current_user)
            if _duplicate_key(item) == _duplicate_key(reminder)
        ),
        None,
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"You already have “{existing.title}” for "
                f"{existing.animal.name} on {existing.due_date:%d %b %Y}."
            ),
        )

    db.add(reminder)
    db.commit()
    return _with_schedule(_owned_reminder(db, reminder.id, current_user))


@router.patch("/{reminder_id}", response_model=ReminderRead)
def update_reminder(
    reminder_id: uuid.UUID,
    payload: ReminderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReminderRead:
    reminder = _owned_reminder(db, reminder_id, current_user)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("animal_id") is not None:
        _owned_animal(db, changes["animal_id"], current_user)
    for field, value in changes.items():
        setattr(reminder, field, value)
    db.commit()
    db.refresh(reminder)
    return _with_schedule(reminder)


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(
    reminder_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    reminder = _owned_reminder(db, reminder_id, current_user)
    db.delete(reminder)
    db.commit()


# ------------------------------------------------------ one dated instance


def _record_for(
    db: Session, reminder: Reminder, scheduled: date, create: bool
) -> ReminderOccurrence | None:
    """The row for one instance, made on demand.

    Rows exist only where something has happened to an instance, so this is
    where they come into being. `create=False` is the undo path, which must not
    conjure a row in order to clear it.
    """
    record = next(
        (item for item in reminder.occurrences if item.occurrence_date == scheduled),
        None,
    )
    if record is None and create:
        record = ReminderOccurrence(reminder_id=reminder.id, occurrence_date=scheduled)
        db.add(record)
        reminder.occurrences.append(record)
    return record


def _must_be_scheduled(reminder: Reminder, scheduled: date) -> None:
    """Refuse a date the recurrence rule never produces.

    Without this, "done" could be recorded against 14 March for a reminder that
    falls on the 15th - a row that satisfies nothing, is invisible in the
    calendar, and silently does not stop the notification the owner was trying
    to stop.
    """
    from app.services.recurrence import occurrences_between

    if scheduled not in occurrences_between(reminder, scheduled, scheduled):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reminder does not fall on that date.",
        )


@router.post("/{reminder_id}/occurrences/{scheduled}/complete", response_model=ReminderRead)
def complete_occurrence(
    reminder_id: uuid.UUID,
    scheduled: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReminderRead:
    """Tick off one dated instance.

    One instance, not the reminder. "Done" on a monthly worming treatment means
    this month's dose is done; the treatment carries on. Marking the reminder
    itself would force a choice between ending the series and keeping no record
    at all, and owners would end up deleting reminders to get them off the
    calendar - which is exactly how the next one gets missed.
    """
    reminder = _owned_reminder(db, reminder_id, current_user)
    _must_be_scheduled(reminder, scheduled)
    record = _record_for(db, reminder, scheduled, create=True)
    assert record is not None
    record.completed_at = datetime.now(timezone.utc)
    # A snooze was a plan to do it later; doing it settles the question, and
    # leaving the date hanging around would draw a ghost on the calendar.
    record.snoozed_to = None
    db.commit()
    db.refresh(reminder)
    return _with_schedule(reminder)


@router.delete(
    "/{reminder_id}/occurrences/{scheduled}/complete", response_model=ReminderRead
)
def uncomplete_occurrence(
    reminder_id: uuid.UUID,
    scheduled: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReminderRead:
    """Undo a tick. Ticking the wrong row is the easiest mistake on the page."""
    reminder = _owned_reminder(db, reminder_id, current_user)
    record = _record_for(db, reminder, scheduled, create=False)
    if record is None or not record.is_done:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That one is not marked done.",
        )
    record.completed_at = None
    # The row has nothing left to say once the tick and the snooze are gone.
    if record.snoozed_to is None:
        reminder.occurrences.remove(record)
        db.delete(record)
    db.commit()
    db.refresh(reminder)
    return _with_schedule(reminder)


@router.post("/{reminder_id}/occurrences/{scheduled}/snooze", response_model=ReminderRead)
def snooze_occurrence(
    reminder_id: uuid.UUID,
    scheduled: date,
    payload: OccurrenceSnooze = Body(default_factory=OccurrenceSnooze),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReminderRead:
    """Push one instance back, leaving the series alone.

    Deliberately not "move the reminder". Snoozing this week's tablet must not
    shift every future week by three days, or a fortnight of snoozes would walk
    a Monday treatment into the weekend. The rule keeps producing what it
    always produced; only this instance moves.

    Measured from where the instance currently sits, so snoozing twice by three
    days lands six days out - which is what pressing the button twice looks
    like it should do.
    """
    reminder = _owned_reminder(db, reminder_id, current_user)
    _must_be_scheduled(reminder, scheduled)

    record = _record_for(db, reminder, scheduled, create=True)
    assert record is not None
    if record.is_done:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That one is already done.",
        )

    if payload.until is not None:
        target = payload.until
    elif payload.days is not None:
        target = record.effective_date + timedelta(days=payload.days)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Say how long to snooze it for.",
        )

    if target <= scheduled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Snoozing has to move it later than the day it was due.",
        )
    # Bounded so a snooze cannot outrun the window the calendar scans for
    # instances pushed in from outside it.
    if target > scheduled + timedelta(days=365):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Snooze by up to a year. Beyond that, change the due date.",
        )

    record.snoozed_to = target
    db.commit()
    db.refresh(reminder)
    return _with_schedule(reminder)


@router.delete(
    "/{reminder_id}/occurrences/{scheduled}/snooze", response_model=ReminderRead
)
def unsnooze_occurrence(
    reminder_id: uuid.UUID,
    scheduled: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReminderRead:
    """Put a postponed instance back where the rule had it."""
    reminder = _owned_reminder(db, reminder_id, current_user)
    record = _record_for(db, reminder, scheduled, create=False)
    if record is None or record.snoozed_to is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That one is not snoozed."
        )
    record.snoozed_to = None
    if record.completed_at is None:
        reminder.occurrences.remove(record)
        db.delete(record)
    db.commit()
    db.refresh(reminder)
    return _with_schedule(reminder)
