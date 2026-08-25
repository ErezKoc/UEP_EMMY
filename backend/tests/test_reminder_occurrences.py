"""Marking reminders done, snoozing them, and clearing out duplicates.

Three properties matter more than the rest, and each is a way somebody misses a
vaccination:

* Ticking off one dose must not end the course. A monthly worming treatment
  marked done in March is due again in April, not finished.
* Snoozing one dose must not shift the ones after it. A fortnight of three-day
  snoozes must never walk a Monday treatment into the weekend permanently.
* Removing a duplicate must never remove the last copy of something.
"""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers every table with Base.metadata
from app.api.v1.reminders import (
    complete_occurrence,
    create_reminder,
    list_duplicates,
    list_occurrences,
    list_reminders,
    resolve_duplicates,
    snooze_occurrence,
    uncomplete_occurrence,
    unsnooze_occurrence,
)
from app.db.base import Base
from app.models import (
    AgeCategory,
    Animal,
    Notification,
    Recurrence,
    Reminder,
    ReminderOccurrence,
    ReminderType,
    User,
)
from app.schemas.reminder import (
    DuplicateResolution,
    OccurrenceSnooze,
    ReminderCreate,
)
from app.services.notifications import due_reminder_notifications, local_now

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def owner(session):
    # Midnight, so the sending-hour gate never makes an unrelated test depend
    # on what time the suite runs. The tests about the gate set their own.
    user = User(email="owner@example.com", display_name="Owner", notify_time=time(0, 0))
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def dog(session, owner):
    animal = Animal(
        name="Buddy", species="dog", age_category=AgeCategory.ADULT, owner_id=owner.id
    )
    session.add(animal)
    session.commit()
    return animal


def _add(session, owner, dog, **kwargs) -> Reminder:
    defaults = dict(
        title="Worming tablet",
        reminder_type=ReminderType.OTHER,
        due_date=TODAY,
        recurrence=Recurrence.MONTHLY,
        recurrence_interval=1,
    )
    defaults.update(kwargs)
    reminder = Reminder(owner_id=owner.id, animal_id=dog.id, **defaults)
    session.add(reminder)
    session.commit()
    return reminder


def _all(session, owner, include_finished=True):
    """`list_reminders` with every query parameter spelled out.

    Calling an endpoint directly skips FastAPI, so an omitted argument arrives
    as the `Query(...)` object itself rather than its default - which SQLAlchemy
    then tries to bind as a UUID.
    """
    return list_reminders(
        start=None,
        end=None,
        animal_id=None,
        include_finished=include_finished,
        db=session,
        current_user=owner,
    )


def _window(session, owner, start, end):
    return list_occurrences(
        start=start, end=end, animal_id=None, db=session, current_user=owner
    )


# ------------------------------------------------------------- marking done


def test_ticking_off_one_dose_does_not_end_the_course(session, owner, dog):
    """The property that makes "done" safe on a repeating reminder.

    Without it an owner has two bad options: leave it showing as due, or delete
    the reminder to clear the calendar - and deleting it is how next month's
    dose gets missed.
    """
    reminder = _add(session, owner, dog, due_date=TODAY, recurrence=Recurrence.MONTHLY)

    after = complete_occurrence(reminder.id, TODAY, db=session, current_user=owner)

    assert after.completed_count == 1
    assert after.is_finished is False
    # Due again next month, not today in a lighter shade of grey.
    assert after.next_occurrence is not None
    assert after.next_occurrence > TODAY


def test_a_one_off_that_is_done_is_finished(session, owner, dog):
    """And leaves the default view, which is most of what "cluttered" was."""
    reminder = _add(session, owner, dog, due_date=TODAY, recurrence=Recurrence.NONE)

    after = complete_occurrence(reminder.id, TODAY, db=session, current_user=owner)

    assert after.is_finished is True
    assert after.next_occurrence is None
    assert _all(session, owner, include_finished=False) == []
    # Still there when asked for: done is not deleted.
    assert len(_all(session, owner)) == 1


def test_a_tick_can_be_taken_back(session, owner, dog):
    """The easiest mistake on the page is ticking the row above the one meant."""
    reminder = _add(session, owner, dog, due_date=TODAY, recurrence=Recurrence.NONE)
    complete_occurrence(reminder.id, TODAY, db=session, current_user=owner)

    after = uncomplete_occurrence(reminder.id, TODAY, db=session, current_user=owner)

    assert after.is_finished is False
    assert after.next_occurrence == TODAY
    assert after.completed_count == 0
    # And the row it created is gone rather than lingering as an empty record.
    assert session.scalars(select(ReminderOccurrence)).all() == []


def test_a_date_the_reminder_never_falls_on_is_refused(session, owner, dog):
    """Otherwise "done" lands on a row that stops nothing and shows nowhere."""
    reminder = _add(
        session, owner, dog, due_date=TODAY, recurrence=Recurrence.MONTHLY
    )

    with pytest.raises(HTTPException) as raised:
        complete_occurrence(
            reminder.id, TODAY + timedelta(days=3), db=session, current_user=owner
        )
    assert raised.value.status_code == 400


def test_somebody_elses_reminder_cannot_be_ticked(session, owner, dog):
    reminder = _add(session, owner, dog)
    stranger = User(email="nosy@example.com", display_name="Nosy")
    session.add(stranger)
    session.commit()

    with pytest.raises(HTTPException) as raised:
        complete_occurrence(reminder.id, TODAY, db=session, current_user=stranger)
    assert raised.value.status_code == 404


# ------------------------------------------------------------------ snoozing


def test_snoozing_moves_one_instance_and_leaves_the_series(session, owner, dog):
    """A fortnight of snoozes must not walk a Monday treatment into the weekend."""
    reminder = _add(session, owner, dog, due_date=TODAY, recurrence=Recurrence.WEEKLY)

    after = snooze_occurrence(
        reminder.id, TODAY, OccurrenceSnooze(days=3), db=session, current_user=owner
    )

    assert after.next_occurrence == TODAY + timedelta(days=3)
    assert after.next_scheduled_date == TODAY
    assert after.next_is_snoozed is True

    # Next week is still next week - measured from the rule, not the snooze.
    window = _window(session, owner, TODAY, TODAY + timedelta(days=10))
    assert [item.date for item in window] == [
        TODAY + timedelta(days=3),
        TODAY + timedelta(days=7),
    ]


def test_snoozing_twice_compounds(session, owner, dog):
    """Pressing "3 days" twice should land six days out, which is what it looks
    like it does. Measuring from the scheduled date instead would silently make
    the second press do nothing."""
    reminder = _add(session, owner, dog, due_date=TODAY, recurrence=Recurrence.NONE)

    snooze_occurrence(
        reminder.id, TODAY, OccurrenceSnooze(days=3), db=session, current_user=owner
    )
    after = snooze_occurrence(
        reminder.id, TODAY, OccurrenceSnooze(days=3), db=session, current_user=owner
    )

    assert after.next_occurrence == TODAY + timedelta(days=6)


def test_a_snooze_can_name_a_date(session, owner, dog):
    reminder = _add(session, owner, dog, due_date=TODAY, recurrence=Recurrence.NONE)

    after = snooze_occurrence(
        reminder.id,
        TODAY,
        OccurrenceSnooze(until=TODAY + timedelta(days=20)),
        db=session,
        current_user=owner,
    )

    assert after.next_occurrence == TODAY + timedelta(days=20)


def test_a_snooze_cannot_go_backwards(session, owner, dog):
    reminder = _add(session, owner, dog, due_date=TODAY, recurrence=Recurrence.NONE)

    with pytest.raises(HTTPException) as raised:
        snooze_occurrence(
            reminder.id,
            TODAY,
            OccurrenceSnooze(until=TODAY - timedelta(days=1)),
            db=session,
            current_user=owner,
        )
    assert raised.value.status_code == 400


def test_a_snooze_beyond_a_year_is_refused(session, owner, dog):
    """Bounded, because the calendar only scans a year either side for
    instances snoozed in from outside the window it is drawing."""
    reminder = _add(session, owner, dog, due_date=TODAY, recurrence=Recurrence.NONE)

    with pytest.raises(HTTPException) as raised:
        snooze_occurrence(
            reminder.id,
            TODAY,
            OccurrenceSnooze(until=TODAY + timedelta(days=400)),
            db=session,
            current_user=owner,
        )
    assert raised.value.status_code == 400


def test_a_snooze_can_be_undone(session, owner, dog):
    reminder = _add(session, owner, dog, due_date=TODAY, recurrence=Recurrence.NONE)
    snooze_occurrence(
        reminder.id, TODAY, OccurrenceSnooze(days=5), db=session, current_user=owner
    )

    after = unsnooze_occurrence(reminder.id, TODAY, db=session, current_user=owner)

    assert after.next_occurrence == TODAY
    assert after.next_is_snoozed is False
    assert session.scalars(select(ReminderOccurrence)).all() == []


def test_marking_a_snoozed_one_done_clears_the_snooze(session, owner, dog):
    """Doing it settles the question; a leftover date would draw a ghost."""
    reminder = _add(session, owner, dog, due_date=TODAY, recurrence=Recurrence.NONE)
    snooze_occurrence(
        reminder.id, TODAY, OccurrenceSnooze(days=5), db=session, current_user=owner
    )

    after = complete_occurrence(reminder.id, TODAY, db=session, current_user=owner)

    assert after.is_finished is True
    record = session.scalars(select(ReminderOccurrence)).one()
    assert record.snoozed_to is None
    assert record.is_done


def test_something_snoozed_out_of_the_month_is_drawn_where_it_landed(
    session, owner, dog
):
    """It has to appear in the month the owner will look for it in, and only
    there - otherwise a dose pushed across a month boundary vanishes twice."""
    end_of_month = date(TODAY.year, TODAY.month, 28)
    reminder = _add(
        session, owner, dog, due_date=end_of_month, recurrence=Recurrence.NONE
    )
    snooze_occurrence(
        reminder.id,
        end_of_month,
        OccurrenceSnooze(days=10),
        db=session,
        current_user=owner,
    )
    landed = end_of_month + timedelta(days=10)

    in_original_month = _window(session, owner, end_of_month, end_of_month)
    where_it_landed = _window(session, owner, landed, landed)

    assert in_original_month == []
    assert [item.date for item in where_it_landed] == [landed]
    assert where_it_landed[0].scheduled_date == end_of_month


# ---------------------------------------------------------------- duplicates


def test_an_identical_reminder_is_refused_at_the_source(session, owner, dog):
    """So the duplicate list stays a way of clearing up history rather than a
    bucket that refills every week."""
    payload = ReminderCreate(
        title="Rabies vaccine",
        reminder_type=ReminderType.VACCINE,
        due_date=TOMORROW,
        animal_id=dog.id,
    )
    create_reminder(payload, db=session, current_user=owner)

    with pytest.raises(HTTPException) as raised:
        create_reminder(payload, db=session, current_user=owner)
    assert raised.value.status_code == 409
    assert "Rabies vaccine" in raised.value.detail


def test_casing_and_stray_spaces_do_not_make_it_a_different_reminder(
    session, owner, dog
):
    """The copies people actually end up with are "Rabies vaccine" and
    "rabies  vaccine" typed a fortnight apart."""
    create_reminder(
        ReminderCreate(
            title="Rabies vaccine",
            reminder_type=ReminderType.VACCINE,
            due_date=TOMORROW,
            animal_id=dog.id,
        ),
        db=session,
        current_user=owner,
    )

    with pytest.raises(HTTPException):
        create_reminder(
            ReminderCreate(
                title="  rabies   VACCINE ",
                reminder_type=ReminderType.VACCINE,
                due_date=TOMORROW,
                animal_id=dog.id,
            ),
            db=session,
            current_user=owner,
        )


def test_the_same_title_for_a_different_pet_is_not_a_duplicate(session, owner, dog):
    other = Animal(
        name="Milo", species="cat", age_category=AgeCategory.ADULT, owner_id=owner.id
    )
    session.add(other)
    session.commit()

    for animal in (dog, other):
        create_reminder(
            ReminderCreate(
                title="Rabies vaccine",
                reminder_type=ReminderType.VACCINE,
                due_date=TOMORROW,
                animal_id=animal.id,
            ),
            db=session,
            current_user=owner,
        )

    assert list_duplicates(db=session, current_user=owner) == []


def test_existing_copies_are_reported_with_the_oldest_kept(session, owner, dog):
    """Oldest wins because it is the one carrying the history - its
    completions, and whatever an appointment confirmation wrote in its notes."""
    first = _add(session, owner, dog, title="Rabies vaccine", recurrence=Recurrence.NONE)
    first.created_at = datetime.now(timezone.utc) - timedelta(days=30)
    second = _add(
        session, owner, dog, title="Rabies vaccine", recurrence=Recurrence.NONE
    )
    third = _add(session, owner, dog, title="rabies vaccine", recurrence=Recurrence.NONE)
    session.commit()

    groups = list_duplicates(db=session, current_user=owner)

    assert len(groups) == 1
    assert groups[0].keep_id == first.id
    assert set(groups[0].duplicate_ids) == {second.id, third.id}
    assert len(groups[0].reminders) == 3


def test_resolving_removes_only_the_copies(session, owner, dog):
    first = _add(session, owner, dog, title="Rabies vaccine", recurrence=Recurrence.NONE)
    first.created_at = datetime.now(timezone.utc) - timedelta(days=30)
    second = _add(
        session, owner, dog, title="Rabies vaccine", recurrence=Recurrence.NONE
    )
    session.commit()

    remaining = resolve_duplicates(
        DuplicateResolution(delete_ids=[second.id]), db=session, current_user=owner
    )

    assert [item.id for item in remaining] == [first.id]
    assert list_duplicates(db=session, current_user=owner) == []


def test_the_last_copy_can_never_be_deleted_as_a_duplicate(session, owner, dog):
    """A page open in another tab can be minutes stale. "Delete these ids" from
    a stale page must not be able to take the only remaining copy of a booster
    after somebody already tidied up elsewhere."""
    only = _add(session, owner, dog, title="Rabies vaccine", recurrence=Recurrence.NONE)

    with pytest.raises(HTTPException) as raised:
        resolve_duplicates(
            DuplicateResolution(delete_ids=[only.id]), db=session, current_user=owner
        )
    assert raised.value.status_code == 409
    assert session.get(Reminder, only.id) is not None


# ------------------------------------------------------------- notifications


def test_a_reminder_marked_done_is_not_announced(session, owner, dog):
    """The point of the tick. Being told to do a thing you have just done is
    how people learn that the alerts are not worth reading."""
    reminder = _add(
        session, owner, dog, due_date=TOMORROW, recurrence=Recurrence.NONE
    )
    complete_occurrence(reminder.id, TOMORROW, db=session, current_user=owner)

    assert due_reminder_notifications(session, today=TODAY) == 0


def test_a_snoozed_reminder_speaks_again_on_its_new_date(session, owner, dog):
    """Snooze is an alarm clock, not a mute button."""
    reminder = _add(session, owner, dog, due_date=TODAY, recurrence=Recurrence.NONE)

    assert due_reminder_notifications(session, today=TODAY) == 1
    snooze_occurrence(
        reminder.id, TODAY, OccurrenceSnooze(days=3), db=session, current_user=owner
    )

    # Quiet in between, because it is not due yet.
    assert due_reminder_notifications(session, today=TODAY + timedelta(days=1)) == 0
    # And it speaks on the day it was moved to.
    assert due_reminder_notifications(session, today=TODAY + timedelta(days=3)) == 1

    latest = session.scalars(select(Notification)).all()[-1]
    assert "snoozed this one" in latest.body


def test_a_reminders_own_lead_time_beats_the_account_default(session, owner, dog):
    """A booster needs a week because it needs an appointment; tonight's tablet
    needs none, because there is nothing to arrange."""
    owner.notify_lead_days = 0
    booster = _add(
        session,
        owner,
        dog,
        title="Rabies booster",
        due_date=TODAY + timedelta(days=5),
        recurrence=Recurrence.NONE,
        notify_lead_days=7,
    )
    _add(
        session,
        owner,
        dog,
        title="Tablet",
        due_date=TODAY + timedelta(days=5),
        recurrence=Recurrence.NONE,
    )
    session.commit()

    created = due_reminder_notifications(session, today=TODAY)

    assert created == 1
    announced = session.scalars(select(Notification)).one()
    assert booster.title in announced.title


def test_nothing_goes_out_before_the_chosen_hour(session, owner, dog):
    """Nobody acts on a reminder at 03:14 - they wake to it already read."""
    owner.notify_time = time(9, 0)
    session.commit()
    _add(session, owner, dog, due_date=TODAY, recurrence=Recurrence.NONE)

    before = datetime(TODAY.year, TODAY.month, TODAY.day, 3, 14, tzinfo=timezone.utc)
    after = datetime(TODAY.year, TODAY.month, TODAY.day, 9, 1, tzinfo=timezone.utc)

    assert due_reminder_notifications(session, today=TODAY, moment=before) == 0
    assert due_reminder_notifications(session, today=TODAY, moment=after) == 1


def test_the_chosen_hour_is_read_in_the_owners_own_timezone(session, owner, dog):
    """09:00 on a server in UTC is the middle of the night for half the people
    using this."""
    owner.notify_time = time(9, 0)
    owner.notify_timezone = "Asia/Tokyo"  # UTC+9, no daylight saving.
    session.commit()
    _add(session, owner, dog, due_date=TODAY, recurrence=Recurrence.NONE)

    # 01:00 UTC is 10:00 in Tokyo: past their hour, though not past ours.
    moment = datetime(TODAY.year, TODAY.month, TODAY.day, 1, 0, tzinfo=timezone.utc)

    assert local_now(owner, moment=moment).hour == 10
    assert due_reminder_notifications(session, today=TODAY, moment=moment) == 1


def test_an_unrecognised_timezone_falls_back_rather_than_going_silent(
    session, owner, dog
):
    """Better a reminder at the wrong hour than no reminder."""
    owner.notify_time = time(0, 0)
    owner.notify_timezone = "Mars/Olympus"
    session.commit()
    _add(session, owner, dog, due_date=TODAY, recurrence=Recurrence.NONE)

    assert due_reminder_notifications(session, today=TODAY) == 1
