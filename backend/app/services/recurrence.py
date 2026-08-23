"""When a repeating reminder actually falls due.

This moved to the server because something other than a calendar grid now has
to answer the question. Notifications are decided here, and a rule that lives
only in the browser cannot tell a scheduler when to send an email.

The frontend still computes occurrences to paint the month view; it must agree
with this module, and `test_recurrence.py` is where that agreement is pinned.

Deliberately not a general iCalendar RRULE implementation. Pet reminders are
"every 3 months", "every 8 days", "every year" — an interval and a unit covers
them, and the cost of the general version is a dependency plus a surface nobody
on this team would be able to debug at 2am.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from app.reminder import Recurrence, Reminder


def _add_months(start: date, months: int) -> date:
    """Shift by whole months, clamping to the end of a shorter month.

    The 31st of January plus one month is the 28th of February, not the 3rd of
    March. Rolling over would drift a monthly reminder forwards a few days a
    year, and a worming treatment due "on the 31st" would quietly become the
    1st, then the 2nd.
    """
    total = start.month - 1 + months
    year = start.year + total // 12
    month = total % 12 + 1
    day = min(start.day, monthrange(year, month)[1])
    return date(year, month, day)


def _step(anchor: date, unit: Recurrence, interval: int, count: int) -> date:
    """The `count`-th occurrence after the anchor."""
    if unit is Recurrence.DAILY:
        return anchor + timedelta(days=interval * count)
    if unit is Recurrence.WEEKLY:
        return anchor + timedelta(weeks=interval * count)
    if unit is Recurrence.MONTHLY:
        return _add_months(anchor, interval * count)
    if unit is Recurrence.YEARLY:
        return _add_months(anchor, 12 * interval * count)
    raise ValueError(f"{unit!r} does not repeat")


def _interval_of(reminder: Reminder) -> int:
    """At least 1, whatever is stored.

    A zero or negative interval would make every generator below spin forever
    on the same date. The column is validated on the way in, but this is the
    function a scheduler loop calls, and it does not get to trust the database.
    """
    return max(1, reminder.recurrence_interval or 1)


def occurrences_between(reminder: Reminder, start: date, end: date) -> list[date]:
    """Every date this reminder falls on within [start, end].

    Inclusive at both ends. Returns at most one date for a non-repeating
    reminder, and never returns anything before `due_date` — the first
    occurrence is the due date itself, not an extrapolation backwards.
    """
    if start > end:
        return []

    first = reminder.due_date
    if reminder.recurrence is Recurrence.NONE:
        return [first] if start <= first <= end else []

    unit = reminder.recurrence
    interval = _interval_of(reminder)
    limit = reminder.repeat_until

    dates: list[date] = []
    count = 0
    while True:
        current = _step(first, unit, interval, count)
        if current > end:
            break
        if limit is not None and current > limit:
            break
        if current >= start:
            dates.append(current)
        count += 1
        # A guard, not a feature. `end` bounds the loop under every unit, but
        # this function runs inside a scheduler that must never hang, and a
        # corrupt row should cost a wrong answer rather than the process.
        if count > 10_000:
            break
    return dates


def next_occurrence(reminder: Reminder, on_or_after: date) -> date | None:
    """The soonest date this reminder falls on from `on_or_after` onwards.

    None when it has finished repeating, or when a one-off is already past.
    """
    if reminder.recurrence is Recurrence.NONE:
        return reminder.due_date if reminder.due_date >= on_or_after else None

    limit = reminder.repeat_until
    unit = reminder.recurrence
    interval = _interval_of(reminder)

    count = 0
    while count <= 10_000:
        current = _step(reminder.due_date, unit, interval, count)
        if limit is not None and current > limit:
            return None
        if current >= on_or_after:
            return current
        count += 1
    return None


def describe(reminder: Reminder) -> str:
    """The rule in words, for a notification body and for the interface.

    Written the way somebody would say it: "every 3 months", not "MONTHLY x3".
    """
    if reminder.recurrence is Recurrence.NONE:
        return "does not repeat"

    interval = _interval_of(reminder)
    noun = {
        Recurrence.DAILY: "day",
        Recurrence.WEEKLY: "week",
        Recurrence.MONTHLY: "month",
        Recurrence.YEARLY: "year",
    }[reminder.recurrence]

    if interval == 1:
        phrase = {"day": "every day", "week": "every week", "month": "every month", "year": "every year"}[noun]
    elif interval == 2:
        # "every other week" is what people say, and it is unambiguous.
        phrase = f"every other {noun}"
    else:
        phrase = f"every {interval} {noun}s"

    if reminder.repeat_until is not None:
        phrase += f", until {reminder.repeat_until:%d %b %Y}"
    return phrase
