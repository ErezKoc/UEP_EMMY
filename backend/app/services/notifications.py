"""Creating notifications, and deciding which ones go out by email.

One entry point — `notify` — used by the appointment endpoints and by the
scheduler alike, so the rules about duplicates and preferences live in exactly
one place rather than being remembered correctly at four call sites.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Reminder, User
from app.models.notification import Notification, NotificationKind
from app.services.email import get_email_sender
from app.services.recurrence import describe, next_pending_occurrence

logger = logging.getLogger(__name__)


def notify(
    db: Session,
    *,
    user: User,
    kind: NotificationKind,
    title: str,
    body: str,
    dedupe_key: str,
    link: str | None = None,
    send_email: bool = True,
) -> Notification | None:
    """Tell one person one thing, at most once.

    Returns None when this exact thing has already been said to this person —
    the caller does not need to check first, which is the point.

    Does not commit. The appointment endpoints create notifications inside the
    transaction that changes the appointment, so a confirmation that fails to
    save cannot leave an announcement behind saying it succeeded.
    """
    if not user.notify_in_app and not user.notify_email:
        return None

    existing = db.scalars(
        select(Notification).where(
            Notification.user_id == user.id, Notification.dedupe_key == dedupe_key
        )
    ).first()
    if existing is not None:
        return None

    notification = Notification(
        user_id=user.id,
        kind=kind,
        title=title,
        body=body,
        link=link,
        dedupe_key=dedupe_key,
    )

    if send_email and user.notify_email and user.email:
        # Belt and braces. `EmailSender.send` already swallows its own
        # failures, but this call sits between building a notification and
        # saving it: anything that escaped here - a sender that fails to
        # construct, a DNS lookup raising - would lose the in-app alert too,
        # over a channel the person may not even be watching.
        try:
            result = get_email_sender().send(to=user.email, subject=title, body=body)
            notification.emailed = result.delivered
        except Exception:
            logger.exception("Email for %r failed; keeping the in-app notification.", title)
            notification.emailed = False

    db.add(notification)
    return notification


def local_now(user: User, *, moment: datetime | None = None) -> datetime:
    """The wall clock where this person is.

    Falls back to UTC when they have not told us a zone, which is honest rather
    than clever: a guess based on the server's own location would put somebody's
    "09:00" at whatever hour our host happens to sit in, and they would have no
    way to tell that from a bug.
    """
    moment = moment or datetime.now(timezone.utc)
    if not user.notify_timezone:
        return moment.astimezone(timezone.utc)
    try:
        return moment.astimezone(ZoneInfo(user.notify_timezone))
    except (ZoneInfoNotFoundError, ValueError):
        # A zone the platform does not recognise - an old browser string, or a
        # tzdata package missing from the image. Silence is the wrong failure
        # here: better a reminder at the wrong hour than no reminder.
        logger.warning("Unknown timezone %r; using UTC.", user.notify_timezone)
        return moment.astimezone(timezone.utc)


def _is_past_sending_time(user: User, *, moment: datetime | None = None) -> bool:
    """Has this person's chosen hour arrived where they are?

    The sweep runs every few minutes and used to announce whenever it happened
    to wake up next, which for anybody with email switched on meant a message
    at 03:14. Nobody acts on a reminder at 03:14 - they wake to it already read.

    Only the hour is gated, not the day: once it is past, every eligible
    reminder goes out on that pass, and the dedupe key stops it repeating on
    the next one.
    """
    return local_now(user, moment=moment).time() >= user.notify_time


def due_reminder_notifications(
    db: Session, *, today: date | None = None, moment: datetime | None = None
) -> int:
    """Announce every reminder falling due inside its lead time.

    Returns how many were created, which is what the scheduler logs.

    The dedupe key carries the date the reminder LANDS on, not just the
    reminder id. A reminder repeating every week is a different event each week
    and should be announced each week; the same week's occurrence must only
    ever be announced once, however many times this function runs. Keying on
    the landing date rather than the scheduled one is also what makes a snooze
    work as an alarm clock: pushed from Tuesday to Friday, it is a new key and
    speaks again on the Friday.
    """
    today = today or date.today()
    created = 0

    reminders = db.scalars(select(Reminder)).all()
    for reminder in reminders:
        owner = db.get(User, reminder.owner_id)
        if owner is None or not (owner.notify_in_app or owner.notify_email):
            continue
        if not _is_past_sending_time(owner, moment=moment):
            continue

        # The reminder's own lead time wins where it has one. A rabies booster
        # needs a week because it needs an appointment; tonight's tablet needs
        # none, because there is nothing to arrange.
        lead = max(
            0,
            reminder.notify_lead_days
            if reminder.notify_lead_days is not None
            else owner.notify_lead_days,
        )
        upcoming = next_pending_occurrence(reminder, today)
        # `None` here means done or finished - the owner has already dealt with
        # it, and an alert would be telling them to do a thing they did.
        if upcoming is None or upcoming.date > today + timedelta(days=lead):
            continue
        occurrence = upcoming.date

        pet = reminder.animal.name if reminder.animal else "your pet"
        days_away = (occurrence - today).days
        when = (
            "today"
            if days_away == 0
            else "tomorrow"
            if days_away == 1
            else f"in {days_away} days"
        )
        repeat = describe(reminder)
        body = (
            f"{reminder.title} for {pet} is due {when} "
            f"({occurrence:%d %b %Y})."
            # Said out loud, because otherwise a snoozed reminder speaking up on
            # a date the calendar rule never produces reads as a bug.
            + (
                f" You snoozed this one from {upcoming.scheduled_date:%d %b %Y}."
                if upcoming.snoozed
                else ""
            )
            + (f" This reminder repeats {repeat}." if repeat != "does not repeat" else "")
        )

        result = notify(
            db,
            user=owner,
            kind=NotificationKind.REMINDER_DUE,
            title=f"Reminder: {reminder.title}",
            body=body,
            dedupe_key=f"reminder:{reminder.id}:{occurrence.isoformat()}",
            link="/calendar",
        )
        if result is not None:
            created += 1

    if created:
        db.commit()
    return created
