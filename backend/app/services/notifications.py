"""Creating notifications, and deciding which ones go out by email.

One entry point — `notify` — used by the appointment endpoints and by the
scheduler alike, so the rules about duplicates and preferences live in exactly
one place rather than being remembered correctly at four call sites.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Reminder, User
from app.models.notification import Notification, NotificationKind
from app.services.email import get_email_sender
from app.services.recurrence import describe, next_occurrence

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


def due_reminder_notifications(db: Session, *, today: date | None = None) -> int:
    """Announce every reminder falling due inside each owner's lead time.

    Returns how many were created, which is what the scheduler logs.

    The dedupe key carries the OCCURRENCE date, not just the reminder id. A
    reminder repeating every week is a different event each week and should be
    announced each week; the same week's occurrence must only ever be announced
    once, however many times this function runs.
    """
    today = today or date.today()
    created = 0

    reminders = db.scalars(select(Reminder)).all()
    for reminder in reminders:
        owner = db.get(User, reminder.owner_id)
        if owner is None or not (owner.notify_in_app or owner.notify_email):
            continue

        lead = max(0, owner.notify_lead_days)
        occurrence = next_occurrence(reminder, today)
        if occurrence is None or occurrence > today + timedelta(days=lead):
            continue

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
