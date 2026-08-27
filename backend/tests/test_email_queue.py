"""The queue: what gets written down, what gets sent, and what happens when it does not.

The queue exists so that no request ever waits on a mail server. Everything
below is a property of that arrangement: a message is a row first, delivery is a
separate pass, and every outcome of that pass is recorded as something a person
could be shown.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers every table with Base.metadata
from app.db.base import Base
from app.models import User
from app.models.email import EmailCategory, EmailMessage, EmailState
from app.models.notification import Notification, NotificationKind
from app.services import email_queue
from app.services.email import SendResult, mask_email
from app.services.email_templates import RenderedEmail
from app.services.notifications import notify

NOW = datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc)


def _aware(moment: datetime) -> datetime:
    """SQLite drops the offset on the way back out; put it back to compare."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


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


def _rendered(subject: str = "Hello") -> RenderedEmail:
    return RenderedEmail(subject=subject, html="<p>Hello</p>", text="Hello")


class _Sender:
    """A sender that does what the test tells it to, and remembers what it saw."""

    def __init__(self, *results: SendResult) -> None:
        # The last result repeats once the script runs out, which is what makes
        # "fails forever" a one-line setup.
        self.results = list(results) or [SendResult(True, "smtp", "sent")]
        self.calls: list[dict] = []

    def send(self, **kwargs):
        self.calls.append(kwargs)
        index = min(len(self.calls) - 1, len(self.results) - 1)
        return self.results[index]


def _use(monkeypatch, sender) -> None:
    monkeypatch.setattr(email_queue, "get_email_sender", lambda: sender)


DELIVERED = SendResult(True, "smtp", "sent via mail.example.com:587")
REFUSED = SendResult(False, "smtp", "SMTPServerDisconnected: connection lost")
NO_SERVER = SendResult(False, "outbox", "/storage/outbox/x.eml", configured=False)


# ---------------------------------------------------------------- enqueueing


def test_a_queued_message_is_a_row_and_nothing_else(session, owner, monkeypatch):
    """The point of the whole design: enqueueing must not touch a mail server."""
    sender = _Sender(DELIVERED)
    _use(monkeypatch, sender)

    email_queue.enqueue(
        session, to=owner.email, rendered=_rendered(), dedupe_key="k1", user=owner
    )
    session.commit()

    assert sender.calls == []
    stored = session.scalars(select(EmailMessage)).all()
    assert len(stored) == 1
    assert stored[0].state is EmailState.QUEUED


def test_the_same_key_is_only_ever_queued_once(session, owner):
    first = email_queue.enqueue(
        session, to=owner.email, rendered=_rendered(), dedupe_key="same", user=owner
    )
    second = email_queue.enqueue(
        session, to=owner.email, rendered=_rendered(), dedupe_key="same", user=owner
    )
    session.commit()

    assert first is not None
    assert second is None
    assert len(session.scalars(select(EmailMessage)).all()) == 1


def test_a_duplicate_does_not_take_the_surrounding_transaction_with_it(session, owner):
    """A second enqueue must be a no-op, not a rolled-back appointment.

    `enqueue` forces the unique constraint inside a savepoint precisely so a
    losing race cannot discard whatever the caller was in the middle of saving.
    """
    email_queue.enqueue(
        session, to=owner.email, rendered=_rendered(), dedupe_key="racy", user=owner
    )
    owner.display_name = "Renamed"
    email_queue.enqueue(
        session, to=owner.email, rendered=_rendered(), dedupe_key="racy", user=owner
    )
    session.commit()

    assert session.get(User, owner.id).display_name == "Renamed"


def test_nothing_is_queued_for_an_account_with_no_address(session):
    user = User(email="", display_name="Nameless")
    session.add(user)
    session.commit()

    assert (
        email_queue.enqueue(session, to="", rendered=_rendered(), dedupe_key="k", user=user)
        is None
    )


def test_a_notification_email_respects_the_reader_switching_email_off(session, owner):
    owner.notify_email = False
    session.commit()

    queued = email_queue.enqueue(
        session,
        to=owner.email,
        rendered=_rendered(),
        dedupe_key="k",
        category=EmailCategory.NOTIFICATION,
        user=owner,
    )

    assert queued is None
    assert session.scalars(select(EmailMessage)).all() == []


def test_a_security_email_is_sent_even_with_email_switched_off(session, owner):
    """Turning notifications off is not consent to be locked out of your account."""
    owner.notify_email = False
    session.commit()

    queued = email_queue.enqueue_security_email(
        session, to=owner.email, rendered=_rendered(), dedupe_key="reset:1", user=owner
    )
    session.commit()

    assert queued is not None
    assert queued.category is EmailCategory.SECURITY
    assert queued.state is EmailState.QUEUED


# ----------------------------------------------------------------- delivering


def test_a_delivered_message_is_recorded_as_sent(session, owner, monkeypatch):
    _use(monkeypatch, _Sender(DELIVERED))
    email_queue.enqueue(
        session, to=owner.email, rendered=_rendered(), dedupe_key="k", user=owner
    )
    session.commit()

    assert email_queue.process_due(session, moment=NOW) == 1

    message = session.scalars(select(EmailMessage)).one()
    assert message.state is EmailState.SENT
    assert message.sent_at is not None
    assert message.attempts == 1


def test_both_bodies_reach_the_sender(session, owner, monkeypatch):
    sender = _Sender(DELIVERED)
    _use(monkeypatch, sender)
    email_queue.enqueue(
        session,
        to=owner.email,
        rendered=RenderedEmail(subject="S", html="<p>rich</p>", text="plain"),
        dedupe_key="k",
        user=owner,
    )
    session.commit()
    email_queue.process_due(session, moment=NOW)

    assert sender.calls[0]["html"] == "<p>rich</p>"
    assert sender.calls[0]["text"] == "plain"


def test_a_failure_is_retried_with_a_growing_delay(session, owner, monkeypatch):
    _use(monkeypatch, _Sender(REFUSED))
    email_queue.enqueue(
        session, to=owner.email, rendered=_rendered(), dedupe_key="k", user=owner
    )
    session.commit()

    delays = []
    moment = NOW
    for _ in range(3):
        email_queue.process_due(session, moment=moment)
        message = session.scalars(select(EmailMessage)).one()
        assert message.state is EmailState.QUEUED
        due = _aware(message.next_attempt_at)
        delays.append(int((due - moment).total_seconds()))
        moment = due

    assert delays == list(email_queue.BACKOFF_SECONDS[:3])


def test_a_message_is_not_tried_again_before_its_time(session, owner, monkeypatch):
    sender = _Sender(REFUSED)
    _use(monkeypatch, sender)
    email_queue.enqueue(
        session, to=owner.email, rendered=_rendered(), dedupe_key="k", user=owner
    )
    session.commit()

    email_queue.process_due(session, moment=NOW)
    # A second later, well inside the first backoff.
    email_queue.process_due(session, moment=NOW + timedelta(seconds=1))

    assert len(sender.calls) == 1


def test_a_message_that_keeps_failing_is_eventually_given_up_on(
    session, owner, monkeypatch
):
    from app.core.config import get_settings

    _use(monkeypatch, _Sender(REFUSED))
    email_queue.enqueue(
        session, to=owner.email, rendered=_rendered(), dedupe_key="k", user=owner
    )
    session.commit()

    moment = NOW
    for _ in range(get_settings().email_max_attempts):
        email_queue.process_due(session, moment=moment)
        moment += timedelta(hours=3)

    message = session.scalars(select(EmailMessage)).one()
    assert message.state is EmailState.FAILED
    assert message.attempts == get_settings().email_max_attempts


def test_a_recovering_mail_server_gets_the_message_through(session, owner, monkeypatch):
    """Two refusals then a success: the retry has to actually deliver."""
    _use(monkeypatch, _Sender(REFUSED, REFUSED, DELIVERED))
    email_queue.enqueue(
        session, to=owner.email, rendered=_rendered(), dedupe_key="k", user=owner
    )
    session.commit()

    moment = NOW
    for _ in range(3):
        email_queue.process_due(session, moment=moment)
        moment += timedelta(hours=3)

    assert session.scalars(select(EmailMessage)).one().state is EmailState.SENT


def test_no_mail_server_is_unavailable_rather_than_failed(session, owner, monkeypatch):
    """The distinction the whole interface rests on.

    Nothing is broken and there is nothing for the reader to retry - this
    deployment simply cannot send email, and saying "failed" would send
    somebody looking for a fault that does not exist.
    """
    _use(monkeypatch, _Sender(NO_SERVER))
    email_queue.enqueue(
        session, to=owner.email, rendered=_rendered(), dedupe_key="k", user=owner
    )
    session.commit()

    assert email_queue.process_due(session, moment=NOW) == 0

    message = session.scalars(select(EmailMessage)).one()
    assert message.state is EmailState.UNAVAILABLE
    assert message.sent_at is None


def test_an_unavailable_message_is_never_retried(session, owner, monkeypatch):
    """There is nothing to retry against, and the outbox file is already written."""
    sender = _Sender(NO_SERVER)
    _use(monkeypatch, sender)
    email_queue.enqueue(
        session, to=owner.email, rendered=_rendered(), dedupe_key="k", user=owner
    )
    session.commit()

    email_queue.process_due(session, moment=NOW)
    email_queue.process_due(session, moment=NOW + timedelta(days=1))

    assert len(sender.calls) == 1


@pytest.mark.parametrize(
    "result,expected",
    [
        (DELIVERED, EmailState.SENT),
        (NO_SERVER, EmailState.UNAVAILABLE),
    ],
    ids=["sent", "unavailable"],
)
def test_a_finished_message_keeps_no_body(session, owner, monkeypatch, result, expected):
    """A queued reset link is a working credential; a finished one must not be.

    The bodies go the moment the message reaches a state it will not leave.
    Everything needed to explain the row afterwards stays.
    """
    _use(monkeypatch, _Sender(result))
    email_queue.enqueue_security_email(
        session,
        to=owner.email,
        rendered=RenderedEmail(subject="Reset", html="<a>secret-token</a>", text="secret-token"),
        dedupe_key="reset:1",
        user=owner,
    )
    session.commit()
    email_queue.process_due(session, moment=NOW)

    message = session.scalars(select(EmailMessage)).one()
    assert message.state is expected
    assert message.html_body is None and message.text_body is None
    assert message.subject == "Reset"


def test_a_message_still_being_retried_keeps_its_body(session, owner, monkeypatch):
    """Obvious, but worth pinning: clearing too early would send an empty email."""
    _use(monkeypatch, _Sender(REFUSED))
    email_queue.enqueue(
        session, to=owner.email, rendered=_rendered(), dedupe_key="k", user=owner
    )
    session.commit()
    email_queue.process_due(session, moment=NOW)

    message = session.scalars(select(EmailMessage)).one()
    assert message.text_body == "Hello"


def test_the_batch_size_bounds_one_pass(session, owner, monkeypatch):
    sender = _Sender(DELIVERED)
    _use(monkeypatch, sender)
    for index in range(5):
        email_queue.enqueue(
            session, to=owner.email, rendered=_rendered(), dedupe_key=f"k{index}", user=owner
        )
    session.commit()

    assert email_queue.process_due(session, limit=2, moment=NOW) == 2
    assert len(sender.calls) == 2


# ----------------------------------------------- what the notification is told


def test_the_notification_mirrors_the_delivery_state(session, owner, monkeypatch):
    _use(monkeypatch, _Sender(DELIVERED))
    notify(
        session,
        user=owner,
        kind=NotificationKind.APPOINTMENT_CONFIRMED,
        title="Appointment confirmed",
        body="See you Tuesday.",
        dedupe_key="appointment:1:confirmed",
        link="/appointments",
    )
    session.commit()

    stored = session.scalars(select(Notification)).one()
    assert stored.email_state is EmailState.QUEUED
    assert stored.emailed is False

    email_queue.process_due(session, moment=NOW)
    session.refresh(stored)

    assert stored.email_state is EmailState.SENT
    assert stored.emailed is True


def test_a_reader_with_email_off_gets_a_notification_that_says_so(session, owner):
    owner.notify_email = False
    session.commit()

    notify(
        session,
        user=owner,
        kind=NotificationKind.APPOINTMENT_CONFIRMED,
        title="Appointment confirmed",
        body="See you Tuesday.",
        dedupe_key="appointment:1:confirmed",
    )
    session.commit()

    stored = session.scalars(select(Notification)).one()
    # Not "failed". Nothing was meant to go out, and a red mark here would send
    # somebody hunting for a problem they created on purpose.
    assert stored.email_state is EmailState.NOT_REQUESTED
    assert session.scalars(select(EmailMessage)).all() == []


def test_a_notification_whose_email_is_refused_still_exists(session, owner, monkeypatch):
    from app.core.config import get_settings

    _use(monkeypatch, _Sender(REFUSED))
    notify(
        session,
        user=owner,
        kind=NotificationKind.REMINDER_DUE,
        title="Reminder",
        body="Due tomorrow.",
        dedupe_key="reminder:1:2026-09-12",
    )
    session.commit()

    moment = NOW
    for _ in range(get_settings().email_max_attempts):
        email_queue.process_due(session, moment=moment)
        moment += timedelta(hours=3)

    stored = session.scalars(select(Notification)).one()
    assert stored.email_state is EmailState.FAILED
    assert stored.emailed is False
    assert stored.title == "Reminder"


# ------------------------------------------------------------------- hygiene


def test_a_failure_is_logged_without_the_recipient_or_the_body(
    session, owner, monkeypatch, caplog
):
    """A log line is copied to places an email body must never reach."""
    _use(monkeypatch, _Sender(REFUSED))
    email_queue.enqueue_security_email(
        session,
        to="alex.smith@example.com",
        rendered=RenderedEmail(
            subject="Reset your password",
            html="<a>https://app/reset?token=SUPERSECRET</a>",
            text="https://app/reset?token=SUPERSECRET",
        ),
        dedupe_key="reset:1",
        user=owner,
    )
    session.commit()

    with caplog.at_level(logging.INFO):
        email_queue.process_due(session, moment=NOW)

    logged = caplog.text
    assert "SUPERSECRET" not in logged
    assert "alex.smith@example.com" not in logged
    assert "al***@example.com" in logged


def test_a_stored_failure_is_bounded_and_flattened():
    detail = "SMTPDataError: 552 " + ("x" * 500) + "\nsecond line"
    described = email_queue.describe_failure(detail)

    assert len(described) <= 300
    assert "\n" not in described


def test_masking_keeps_enough_to_recognise_a_row():
    assert mask_email("alex.smith@example.com") == "al***@example.com"
    assert mask_email("a@b.com") == "a***@b.com"
    assert mask_email("not-an-address") == "***"
    assert mask_email("") == "***"


def test_finished_rows_are_eventually_cleared_out(session, owner, monkeypatch):
    _use(monkeypatch, _Sender(DELIVERED))
    email_queue.enqueue(
        session, to=owner.email, rendered=_rendered(), dedupe_key="old", user=owner
    )
    session.commit()
    email_queue.process_due(session, moment=NOW)

    assert email_queue.purge_sent(session, older_than_days=30, moment=NOW) == 0
    assert email_queue.purge_sent(session, older_than_days=30, moment=NOW + timedelta(days=60)) == 1


def test_purging_leaves_anything_still_waiting(session, owner):
    email_queue.enqueue(
        session, to=owner.email, rendered=_rendered(), dedupe_key="waiting", user=owner
    )
    session.commit()

    assert email_queue.purge_sent(session, moment=NOW + timedelta(days=365)) == 0
    assert len(session.scalars(select(EmailMessage)).all()) == 1
