"""Creating notifications, and deciding which ones go out by email.

One entry point — `notify` — used by the appointment endpoints and by the
scheduler alike, so the rules about duplicates and preferences live in exactly
one place rather than being remembered correctly at four call sites.

The email half is **queued, never sent here**. `notify` runs inside the request
that changed the appointment; a mail server that is slow or unreachable must not
be able to make that request slow or unreachable in turn. What this module does
is write the message down (see `email_queue`); a background sweep delivers it
and records what happened.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Reminder, User
from app.models.notification import Notification, NotificationKind
from app.services import email_queue
from app.services.email_templates import notification_email
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
    email_facts: list[tuple[str, str]] | None = None,
) -> Notification | None:
    """Tell one person one thing, at most once.

    Returns None when this exact thing has already been said to this person —
    the caller does not need to check first, which is the point.

    Does not commit. The appointment endpoints create notifications inside the
    transaction that changes the appointment, so a confirmation that fails to
    save cannot leave an announcement behind saying it succeeded — and cannot
    leave a queued email announcing it either.

    `email_facts` are the labelled details the email carries that a one-line
    alert has no room for: the pet, the date, the practice. Optional, and
    nothing is invented when a caller has none.
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
    db.add(notification)
    # The email row references this one, so it needs an id before the queue can
    # point at it.
    db.flush()

    if send_email and user.email:
        # Belt and braces. `enqueue` is a database insert and should not be able
        # to fail in a way that matters, but it sits between building a
        # notification and saving it: anything that escaped here would lose the
        # in-app alert too, over a channel the person may not even be watching.
        try:
            email_queue.enqueue_for_notification(
                db,
                user=user,
                notification=notification,
                rendered=notification_email(
                    kind=kind,
                    title=title,
                    body=body,
                    link=link,
                    facts=email_facts,
                    recipient_name=user.display_name,
                ),
            )
        except Exception:
            logger.exception("Queueing the email for %r failed; keeping the in-app alert.", kind)

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


def local_today(user: User, *, moment: datetime | None = None) -> date:
    """The date it is where this person is.

    Not the server's date. Somewhere between UTC-11 and UTC+14 there is always
    somebody for whom the server is on the wrong day, and for them "due today"
    printed against the server's calendar is simply wrong — a reminder that
    says "today" on a day that is not today, or arrives a day late because the
    lead-time window was measured from the wrong end.
    """
    return local_now(user, moment=moment).date()


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


def _leads_for(reminder: Reminder, owner: User) -> list[int]:
    """Every lead time this reminder should be announced at, largest first.

    A reminder that names its own lead time gets exactly that one — a booster
    set to a week's warning means a week, not a week and also whatever the
    account happens to want. Otherwise the account's list applies, which is
    usually a single value and may be several: "tell me a week before AND the
    night before" is one preference, not two competing ones.
    """
    if reminder.notify_lead_days is not None:
        return [max(0, reminder.notify_lead_days)]
    return owner.lead_days


def _dedupe_key(reminder: Reminder, occurrence: date, lead: int, *, primary: int) -> str:
    """One key per reminder, per occurrence, per lead time.

    The occurrence date is in the key rather than just the reminder id because a
    reminder repeating every week is a different event each week and should be
    announced each week; the same week's occurrence must only ever be announced
    once, however many times this function runs. Keying on the landing date
    rather than the scheduled one is also what makes a snooze work as an alarm
    clock: pushed from Tuesday to Friday, it is a new key and speaks again on
    the Friday.

    The lead is in the key too, so "a week before" and "the night before" are
    two announcements rather than one that silences the other. The account's
    primary lead keeps the original two-part key, so every alert an existing
    database has already sent stays recognised and is not announced a second
    time the day this code ships.
    """
    base = f"reminder:{reminder.id}:{occurrence.isoformat()}"
    return base if lead == primary else f"{base}:lead{lead}"


def due_reminder_notifications(
    db: Session, *, today: date | None = None, moment: datetime | None = None
) -> int:
    """Announce every reminder falling due inside its lead time.

    Returns how many were created, which is what the scheduler logs.

    `today` is normally left unset, and then each owner's own date is used —
    see `local_today`. Passing one forces a date for every owner, which is what
    the tests want and what a one-off backfill script would want.
    """
    forced_today = today
    created = 0

    reminders = db.scalars(select(Reminder)).all()
    for reminder in reminders:
        owner = db.get(User, reminder.owner_id)
        if owner is None or not (owner.notify_in_app or owner.notify_email):
            continue
        if not _is_past_sending_time(owner, moment=moment):
            continue

        # The owner's own date, so "due today" means today where they are.
        today = forced_today or local_today(owner, moment=moment)

        # The reminder's own lead time wins where it has one. A rabies booster
        # needs a week because it needs an appointment; tonight's tablet needs
        # none, because there is nothing to arrange.
        leads = _leads_for(reminder, owner)
        primary = owner.notify_lead_days if reminder.notify_lead_days is None else leads[0]

        upcoming = next_pending_occurrence(reminder, today)
        # `None` here means done or finished - the owner has already dealt with
        # it, and an alert would be telling them to do a thing they did.
        if upcoming is None:
            continue
        occurrence = upcoming.date

        for lead in leads:
            if occurrence > today + timedelta(days=lead):
                # This lead has not come round yet. A larger one may already
                # have fired, and a smaller one will fire on its own day.
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
                # Said out loud, because otherwise a snoozed reminder speaking up
                # on a date the calendar rule never produces reads as a bug.
                + (
                    f" You snoozed this one from {upcoming.scheduled_date:%d %b %Y}."
                    if upcoming.snoozed
                    else ""
                )
                + (f" This reminder repeats {repeat}." if repeat != "does not repeat" else "")
            )

            facts: list[tuple[str, str]] = [
                ("Pet", pet),
                ("Due", f"{occurrence:%d %b %Y} ({when})"),
            ]
            if repeat != "does not repeat":
                facts.append(("Repeats", repeat))

            result = notify(
                db,
                user=owner,
                kind=NotificationKind.REMINDER_DUE,
                title=f"Reminder: {reminder.title}",
                body=body,
                dedupe_key=_dedupe_key(reminder, occurrence, lead, primary=primary),
                link="/calendar",
                email_facts=facts,
            )
            if result is not None:
                created += 1

    if created:
        db.commit()
    return created
