"""Recurrence arithmetic, and the rule that stops a scheduler shouting.

The scheduler has no memory between runs and is designed to be safe to run as
often as it likes. Everything that makes that true is here.
"""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers every table with Base.metadata
from app.db.base import Base
from app.models import AgeCategory, Animal, Recurrence, Reminder, ReminderType, User
from app.models.notification import Notification, NotificationKind
from app.services.notifications import due_reminder_notifications, notify
from app.services.recurrence import describe, next_occurrence, occurrences_between


def _reminder(**kwargs) -> Reminder:
    """A detached Reminder, for the pure-arithmetic tests."""
    defaults = dict(
        title="Flea treatment",
        reminder_type=ReminderType.OTHER,
        due_date=date(2026, 1, 15),
        recurrence=Recurrence.NONE,
        recurrence_interval=1,
        repeat_until=None,
    )
    defaults.update(kwargs)
    return Reminder(**defaults)


# ------------------------------------------------------------- recurrence


def test_a_one_off_occurs_once_and_only_on_its_day():
    reminder = _reminder()
    assert occurrences_between(reminder, date(2026, 1, 1), date(2026, 12, 31)) == [date(2026, 1, 15)]
    assert occurrences_between(reminder, date(2026, 2, 1), date(2026, 12, 31)) == []


def test_every_three_months_lands_on_the_same_day_each_time():
    reminder = _reminder(recurrence=Recurrence.MONTHLY, recurrence_interval=3)

    dates = occurrences_between(reminder, date(2026, 1, 1), date(2026, 12, 31))

    assert dates == [date(2026, 1, 15), date(2026, 4, 15), date(2026, 7, 15), date(2026, 10, 15)]


def test_the_31st_clamps_to_a_short_month_instead_of_rolling_over():
    """The 31st of January plus a month is 28 February, not 3 March.

    Rolling over would drift a monthly reminder forward a few days a year, so a
    treatment due "on the 31st" quietly becomes the 1st, then the 2nd.
    """
    reminder = _reminder(due_date=date(2026, 1, 31), recurrence=Recurrence.MONTHLY)

    dates = occurrences_between(reminder, date(2026, 1, 1), date(2026, 4, 30))

    assert dates == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]


def test_clamping_does_not_permanently_shorten_later_months():
    """February must not drag March down to the 28th as well."""
    reminder = _reminder(due_date=date(2026, 1, 31), recurrence=Recurrence.MONTHLY)

    assert date(2026, 3, 31) in occurrences_between(reminder, date(2026, 3, 1), date(2026, 3, 31))


def test_every_eight_days_steps_by_eight():
    reminder = _reminder(recurrence=Recurrence.DAILY, recurrence_interval=8)

    dates = occurrences_between(reminder, date(2026, 1, 15), date(2026, 2, 10))

    assert dates == [date(2026, 1, 15), date(2026, 1, 23), date(2026, 1, 31), date(2026, 2, 8)]


def test_an_end_date_stops_it():
    reminder = _reminder(
        recurrence=Recurrence.WEEKLY, repeat_until=date(2026, 2, 5)
    )

    dates = occurrences_between(reminder, date(2026, 1, 1), date(2026, 12, 31))

    assert dates == [date(2026, 1, 15), date(2026, 1, 22), date(2026, 1, 29), date(2026, 2, 5)]
    assert next_occurrence(reminder, date(2026, 2, 6)) is None


def test_nothing_is_ever_generated_before_the_due_date():
    """The first occurrence is the due date, never an extrapolation backwards."""
    reminder = _reminder(recurrence=Recurrence.MONTHLY)

    assert occurrences_between(reminder, date(2025, 1, 1), date(2026, 1, 14)) == []


def test_a_zero_interval_cannot_hang_the_scheduler():
    """The column is validated on the way in; this function does not trust it."""
    reminder = _reminder(recurrence=Recurrence.DAILY, recurrence_interval=0)

    dates = occurrences_between(reminder, date(2026, 1, 15), date(2026, 1, 18))

    assert dates == [date(2026, 1, 15), date(2026, 1, 16), date(2026, 1, 17), date(2026, 1, 18)]


@pytest.mark.parametrize(
    "recurrence,interval,expected",
    [
        (Recurrence.NONE, 1, "does not repeat"),
        (Recurrence.MONTHLY, 1, "every month"),
        (Recurrence.WEEKLY, 2, "every other week"),
        (Recurrence.MONTHLY, 3, "every 3 months"),
        (Recurrence.DAILY, 8, "every 8 days"),
    ],
)
def test_the_rule_reads_the_way_somebody_would_say_it(recurrence, interval, expected):
    assert describe(_reminder(recurrence=recurrence, recurrence_interval=interval)) == expected


# ------------------------------------------------------------ the sweep


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def owner(session):
    """An owner whose sending hour has always already passed.

    `notify_time` defaults to 09:00, which would make every assertion below
    depend on what time of day the suite happens to run - green after breakfast
    and red before it. Midnight takes the clock out of the tests that are not
    about the clock; the ones that are set their own and pass an explicit
    moment.
    """
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


def _save_reminder(session, owner, dog, **kwargs) -> Reminder:
    reminder = _reminder(**kwargs)
    reminder.owner_id = owner.id
    reminder.animal_id = dog.id
    session.add(reminder)
    session.commit()
    return reminder


def test_a_reminder_due_tomorrow_is_announced_once_however_often_we_sweep(
    session, owner, dog
):
    """The property the whole design rests on.

    The sweep runs on a timer with no memory between runs. If it announced
    everything it found each time, a fifteen-minute interval would send the
    same alert 96 times a day.
    """
    today = date.today()
    _save_reminder(session, owner, dog, due_date=today + timedelta(days=1))

    first = due_reminder_notifications(session, today=today)
    second = due_reminder_notifications(session, today=today)
    third = due_reminder_notifications(session, today=today)

    assert (first, second, third) == (1, 0, 0)
    assert len(session.scalars(select(Notification)).all()) == 1


def test_each_occurrence_of_a_repeating_reminder_gets_its_own_alert(session, owner, dog):
    """Same reminder, different week: a different event, announced again."""
    today = date.today()
    _save_reminder(
        session,
        owner,
        dog,
        due_date=today + timedelta(days=1),
        recurrence=Recurrence.WEEKLY,
    )

    due_reminder_notifications(session, today=today)
    later = due_reminder_notifications(session, today=today + timedelta(days=7))

    assert later == 1
    assert len(session.scalars(select(Notification)).all()) == 2


def test_a_reminder_beyond_the_lead_time_waits(session, owner, dog):
    today = date.today()
    owner.notify_lead_days = 1
    _save_reminder(session, owner, dog, due_date=today + timedelta(days=5))

    assert due_reminder_notifications(session, today=today) == 0


def test_the_lead_time_is_the_owners_choice(session, owner, dog):
    today = date.today()
    owner.notify_lead_days = 7
    session.commit()
    _save_reminder(session, owner, dog, due_date=today + timedelta(days=5))

    assert due_reminder_notifications(session, today=today) == 1


def test_turning_both_channels_off_stops_everything(session, owner, dog):
    today = date.today()
    owner.notify_in_app = False
    owner.notify_email = False
    session.commit()
    _save_reminder(session, owner, dog, due_date=today)

    assert due_reminder_notifications(session, today=today) == 0
    assert session.scalars(select(Notification)).all() == []


def test_an_expired_repeating_reminder_is_not_announced(session, owner, dog):
    today = date.today()
    _save_reminder(
        session,
        owner,
        dog,
        due_date=today - timedelta(days=30),
        recurrence=Recurrence.WEEKLY,
        repeat_until=today - timedelta(days=1),
    )

    assert due_reminder_notifications(session, today=today) == 0


def test_notify_returns_none_rather_than_duplicating(session, owner):
    first = notify(
        session,
        user=owner,
        kind=NotificationKind.APPOINTMENT_CONFIRMED,
        title="Appointment confirmed",
        body="See you Tuesday.",
        dedupe_key="appointment:abc:confirmed",
    )
    session.commit()
    second = notify(
        session,
        user=owner,
        kind=NotificationKind.APPOINTMENT_CONFIRMED,
        title="Appointment confirmed",
        body="See you Tuesday.",
        dedupe_key="appointment:abc:confirmed",
    )

    assert first is not None
    assert second is None


def test_email_failure_never_costs_the_in_app_alert(session, owner, dog, monkeypatch):
    """A mail server being down must not swallow the notification too."""
    from app.services import notifications as module

    class _Broken:
        def send(self, **kwargs):
            raise OSError("mail server is on fire")

    monkeypatch.setattr(module, "get_email_sender", lambda: _Broken())
    today = date.today()
    _save_reminder(session, owner, dog, due_date=today)

    created = due_reminder_notifications(session, today=today)

    assert created == 1
    stored = session.scalars(select(Notification)).all()
    assert len(stored) == 1
    # Recorded as not emailed, so a retry knows which half is missing rather
    # than assuming the whole notification went out.
    assert stored[0].emailed is False
