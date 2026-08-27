"""The email queue: writing messages down, and getting them delivered.

Two halves, and keeping them apart is the whole design.

`enqueue` runs inside the request that caused the email. It inserts a row and
returns - no socket, no DNS, no timeout. An owner confirming an appointment
waits on a database insert rather than on somebody else's mail server, which is
the difference between a snappy endpoint and one that takes thirty seconds
whenever a relay is slow.

`process_due` runs in a background sweep. It takes the rows that are ready,
tries each one, and writes down what happened - marking a message SENT, backing
off and rescheduling a failure, or giving up after `email_max_attempts`. A
message that fails is a row to look at, not a lost message and not a traceback
in the log.

Three properties this module owns:

**Preferences.** Notification mail is suppressed when the account has email
switched off; security mail is not, because turning notifications off is not
consent to be locked out of your own account.

**Deduplication.** `dedupe_key` is unique in the database, so a caller that
asks twice gets one message. The keys are the same ones the notification layer
already uses, which is what makes a scheduler running every fifteen minutes
safe to run every fifteen minutes.

**Honesty.** Nothing is ever recorded as sent that was not sent. With no SMTP
server configured the message goes to the local outbox and the state is
UNAVAILABLE, which is a different sentence from FAILED and a very different one
from SENT.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.email import EmailCategory, EmailMessage, EmailState
from app.models.notification import Notification
from app.models.user import User
from app.services.email import get_email_sender, mask_email
from app.services.email_templates import RenderedEmail

logger = logging.getLogger(__name__)

#: How long to wait before each retry, in seconds. One minute, five, half an
#: hour, two hours - fast enough that a relay hiccup costs nobody anything,
#: spread out enough that a mail server which is down for maintenance is not
#: hammered by every queued message at once. The last value repeats if the
#: attempt count ever runs past the end.
BACKOFF_SECONDS: tuple[int, ...] = (60, 300, 1800, 7200)

#: How much of a failure description is kept. The column is 300; anything
#: longer is a stack-ish blob nobody reads.
_DETAIL_LIMIT = 300


def describe_failure(detail: str) -> str:
    """Trim a failure description to something safe to store and to log.

    The sender already reduces exceptions to type plus message, and the message
    from smtplib never contains the password (it is not passed through) or the
    body (it is not echoed). This is the last guard: a bounded string, so a
    verbose server response cannot push anything unbounded into the row.
    """
    cleaned = " ".join((detail or "").split())
    return cleaned[:_DETAIL_LIMIT]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ enqueueing


def enqueue(
    db: Session,
    *,
    to: str,
    rendered: RenderedEmail,
    dedupe_key: str,
    category: EmailCategory = EmailCategory.NOTIFICATION,
    user: User | None = None,
    notification: Notification | None = None,
) -> EmailMessage | None:
    """Write one message down to be sent later.

    Returns the row, or None when nothing was queued - an address we do not
    have, a preference that says no, or a message already in the queue under
    this key. None is not a failure; it is "there is nothing to send", and the
    caller does not have to tell the two apart.

    Does not commit. The caller's transaction owns this, so an appointment that
    fails to save cannot leave an email behind announcing that it did.
    """
    address = (to or "").strip()
    if not address:
        return None

    if category is EmailCategory.NOTIFICATION and user is not None and not user.notify_email:
        # Recorded on the notification so the interface can say "you have email
        # switched off" rather than leaving a blank where a status should be.
        if notification is not None:
            notification.email_state = EmailState.NOT_REQUESTED
            notification.emailed = False
        return None

    existing = db.scalars(
        select(EmailMessage).where(EmailMessage.dedupe_key == dedupe_key)
    ).first()
    if existing is not None:
        return None

    message = EmailMessage(
        to_email=address,
        subject=rendered.subject[:300],
        html_body=rendered.html,
        text_body=rendered.text,
        category=category,
        dedupe_key=dedupe_key[:200],
        state=EmailState.QUEUED,
        attempts=0,
        # Due immediately. The sweep picks up anything whose time has come,
        # and "now" is the normal case; a value in the future is what a
        # backoff writes.
        next_attempt_at=_now(),
        user_id=user.id if user is not None else None,
        notification_id=notification.id if notification is not None else None,
    )
    try:
        # A SAVEPOINT, not a plain flush. The unique constraint has to be
        # forced now rather than at commit - otherwise a race between two
        # requests queueing the same key takes down the whole surrounding
        # transaction, and the surrounding transaction is the appointment.
        # Rolling back to a savepoint undoes this insert and nothing else.
        with db.begin_nested():
            db.add(message)
            db.flush()
    except IntegrityError:
        logger.debug("Email %s was already queued by another request.", dedupe_key)
        return None

    if notification is not None:
        notification.email_state = EmailState.QUEUED
        notification.email_attempts = 0
        notification.email_next_attempt_at = message.next_attempt_at
        notification.email_detail = None
        notification.emailed = False
    return message


def enqueue_for_notification(
    db: Session,
    *,
    user: User,
    notification: Notification,
    rendered: RenderedEmail,
) -> EmailMessage | None:
    """Queue the email half of an in-app alert, keyed on the alert itself.

    The notification's own dedupe key is reused with an `email:` prefix, so the
    thing that stops a notification being announced twice is the same thing
    that stops its email being sent twice.
    """
    return enqueue(
        db,
        to=user.email,
        rendered=rendered,
        dedupe_key=f"email:{notification.dedupe_key}",
        category=EmailCategory.NOTIFICATION,
        user=user,
        notification=notification,
    )


def enqueue_security_email(
    db: Session,
    *,
    to: str,
    rendered: RenderedEmail,
    dedupe_key: str,
    user: User | None = None,
) -> EmailMessage | None:
    """Queue verification or password-reset mail.

    Ignores `notify_email` by construction - the category decides, and this one
    is never suppressed. Somebody who turned reminder emails off still has to
    be able to get back into their account.
    """
    return enqueue(
        db,
        to=to,
        rendered=rendered,
        dedupe_key=dedupe_key,
        category=EmailCategory.SECURITY,
        user=user,
    )


# ------------------------------------------------------------------- delivering


def due_messages(
    db: Session, *, limit: int | None = None, moment: datetime | None = None
) -> list[EmailMessage]:
    """Queued messages whose time has come, oldest first."""
    moment = moment or _now()
    limit = limit or get_settings().email_batch_size
    statement = (
        select(EmailMessage)
        .where(
            EmailMessage.state == EmailState.QUEUED,
            or_(
                EmailMessage.next_attempt_at.is_(None),
                EmailMessage.next_attempt_at <= moment,
            ),
        )
        .order_by(EmailMessage.created_at)
        .limit(limit)
    )
    return list(db.scalars(statement).all())


def process_due(
    db: Session, *, limit: int | None = None, moment: datetime | None = None
) -> int:
    """Try every message that is ready. Returns how many were delivered.

    Commits once at the end rather than per message: a batch of twenty is one
    transaction's worth of bookkeeping, and a crash halfway through leaves the
    unhandled rows QUEUED - which is exactly where the next pass wants them.
    Sending a message twice after such a crash is possible in principle and is
    the right trade against never sending it at all.
    """
    moment = moment or _now()
    sender = get_email_sender()
    delivered = 0

    for message in due_messages(db, limit=limit, moment=moment):
        message.attempts += 1
        result = sender.send(
            to=message.to_email,
            subject=message.subject,
            text=message.text_body or "",
            html=message.html_body,
        )

        if result.delivered:
            _finish(message, EmailState.SENT, detail=describe_failure(result.detail), moment=moment)
            delivered += 1
        elif not result.configured:
            # No mail server here. Not a failure and not retryable: the message
            # is in the local outbox, and trying again every minute would write
            # the same file forever.
            _finish(
                message,
                EmailState.UNAVAILABLE,
                detail="No SMTP server is configured; written to the local outbox.",
                moment=moment,
            )
        elif message.attempts >= get_settings().email_max_attempts:
            _finish(
                message,
                EmailState.FAILED,
                detail=describe_failure(result.detail),
                moment=moment,
            )
            logger.warning(
                "Giving up on email to %s after %d attempts: %s",
                mask_email(message.to_email),
                message.attempts,
                describe_failure(result.detail),
            )
        else:
            delay = BACKOFF_SECONDS[min(message.attempts - 1, len(BACKOFF_SECONDS) - 1)]
            message.next_attempt_at = moment + timedelta(seconds=delay)
            message.detail = describe_failure(result.detail)
            logger.info(
                "Email to %s failed (attempt %d); retrying in %ds.",
                mask_email(message.to_email),
                message.attempts,
                delay,
            )

        # Every branch, including the retry: the notification row is what the
        # interface reads, and a state written here but not there is a row that
        # says "queued" forever.
        _mirror(db, message)

    db.commit()
    return delivered


def _finish(
    message: EmailMessage, state: EmailState, *, detail: str | None, moment: datetime
) -> None:
    """Put a message into a state it will not leave, and drop its bodies.

    The bodies go because a queued password reset necessarily contains a
    working link, and keeping that link in the database after the message has
    been dealt with leaves a credential lying about for no benefit at all.
    Everything needed to explain the row afterwards - who, what subject, which
    state, why - stays.
    """
    message.state = state
    message.next_attempt_at = None
    message.detail = detail
    message.html_body = None
    message.text_body = None
    if state is EmailState.SENT:
        message.sent_at = moment


def _mirror(db: Session, message: EmailMessage) -> None:
    """Copy a message's state onto the notification it belongs to.

    Denormalised on purpose: the notification list is polled, and a join per
    row to answer "did the email go" would put the queue in the hot path of the
    most frequent read in the application.
    """
    if message.notification_id is None:
        return
    notification = db.get(Notification, message.notification_id)
    if notification is None:
        return
    notification.email_state = message.state
    notification.email_attempts = message.attempts
    notification.email_detail = message.detail
    # None once the message is finished - `_finish` clears it - and a real
    # timestamp only while a retry is pending.
    notification.email_next_attempt_at = message.next_attempt_at
    notification.emailed = message.state is EmailState.SENT


def purge_sent(db: Session, *, older_than_days: int = 30, moment: datetime | None = None) -> int:
    """Drop old, finished rows. Returns how many went.

    The queue is a work list, not an archive. Rows that have reached a terminal
    state have already had their bodies cleared and are kept only long enough
    to answer "what happened to my email last week".
    """
    moment = moment or _now()
    cutoff = moment - timedelta(days=older_than_days)
    stale = db.scalars(
        select(EmailMessage).where(
            EmailMessage.state != EmailState.QUEUED, EmailMessage.created_at < cutoff
        )
    ).all()
    for row in stale:
        db.delete(row)
    if stale:
        db.commit()
    return len(stale)
