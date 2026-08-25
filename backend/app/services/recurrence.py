"""When a repeating reminder actually falls due.

This moved to the server because something other than a calendar grid now has
to answer the question. Notifications are decided here, and a rule that lives
only in the browser cannot tell a scheduler when to send an email.

The frontend no longer computes occurrences at all. It used to mirror this
module to paint the month grid, and that mirror was affordable only while the
answer was pure arithmetic; once completions and snoozes joined it, keeping two
implementations honest would have meant duplicating those too. The calendar now
asks `GET /v1/reminders/occurrences` for the window it is drawing, so there is
one implementation and nothing to keep in step.

Deliberately not a general iCalendar RRULE implementation. Pet reminders are
"every 3 months", "every 8 days", "every year" — an interval and a unit covers
them, and the cost of the general version is a dependency plus a surface nobody
on this team would be able to debug at 2am.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from app.reminder import Recurrence, Reminder, ReminderOccurrence


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


# --------------------------------------------------- what has been done to it
#
# Everything above answers "when does the RULE fall due". Everything below
# answers "when is the owner actually expected to do something", which is the
# rule minus what they have already ticked off, with anything they postponed
# moved to where they postponed it to.
#
# Kept as a separate layer rather than folded into the generators because the
# arithmetic is worth testing without a database anywhere near it, and because
# a scheduler asking "is this done?" needs a different answer from an export
# asking "what is the pattern?".


@dataclass(frozen=True)
class Occurrence:
    """One dated instance of a reminder, after completions and snoozes.

    `scheduled_date` is what the rule produced and is the identity used by
    every endpoint, notification key and database row. `date` is where it
    actually lands, which differs only when somebody snoozed it.
    """

    scheduled_date: date
    date: date
    done: bool
    snoozed: bool

    @property
    def is_pending(self) -> bool:
        return not self.done


def _overrides(records: Iterable[ReminderOccurrence]) -> dict[date, ReminderOccurrence]:
    return {record.occurrence_date: record for record in records}


def resolved_occurrences(
    reminder: Reminder,
    start: date,
    end: date,
    records: Iterable[ReminderOccurrence] | None = None,
) -> list[Occurrence]:
    """Every instance visible in [start, end], with its real date and state.

    A snoozed instance is returned when its SNOOZED date falls in the window,
    not its scheduled one - the calendar has to draw it where the owner will
    look for it. So the window is widened before generating and the results
    filtered afterwards, otherwise a dose scheduled on the 30th and pushed to
    the 2nd would vanish from both months.
    """
    records = list(records if records is not None else reminder.occurrences)
    overrides = _overrides(records)

    # Wide enough to catch anything snoozed into this window from outside it.
    # A snooze is capped at a year by the endpoint, so a year either side is
    # the whole of it.
    scan_from = start - timedelta(days=370)
    scan_to = end + timedelta(days=370)

    resolved: list[Occurrence] = []
    for scheduled in occurrences_between(reminder, scan_from, scan_to):
        record = overrides.get(scheduled)
        landing = record.effective_date if record is not None else scheduled
        if not (start <= landing <= end):
            continue
        resolved.append(
            Occurrence(
                scheduled_date=scheduled,
                date=landing,
                done=record is not None and record.is_done,
                snoozed=record is not None and record.snoozed_to is not None,
            )
        )
    resolved.sort(key=lambda item: (item.date, item.scheduled_date))
    return resolved


def next_pending_occurrence(
    reminder: Reminder,
    on_or_after: date,
    records: Iterable[ReminderOccurrence] | None = None,
) -> Occurrence | None:
    """The soonest instance still waiting to be done.

    Completed ones are skipped rather than merely marked, because "next due"
    is the number an owner plans around and a date they have already dealt with
    is not it. A monthly treatment ticked off this morning should read as due
    next month, not as due today in a lighter shade of grey.
    """
    records = list(records if records is not None else reminder.occurrences)
    overrides = _overrides(records)

    def build(scheduled: date) -> Occurrence:
        record = overrides.get(scheduled)
        return Occurrence(
            scheduled_date=scheduled,
            date=record.effective_date if record is not None else scheduled,
            done=False,
            snoozed=record is not None and record.snoozed_to is not None,
        )

    # Two passes, because a snooze and a long interval fail in opposite
    # directions and neither one search handles both.
    #
    # First: anything ALREADY scheduled in the past that was snoozed forward to
    # on or after this date. Walking forwards from `on_or_after` would never
    # find it, because its scheduled date is behind us. Only rows that exist
    # are checked, so this costs nothing when nothing has been snoozed.
    best: Occurrence | None = None
    for record in records:
        if record.is_done or record.snoozed_to is None:
            continue
        if record.snoozed_to < on_or_after:
            continue
        candidate = build(record.occurrence_date)
        if best is None or candidate.date < best.date:
            best = candidate

    # Second: forwards along the schedule itself, skipping what is done. The
    # step count is bounded rather than the date range, so "every 365 days"
    # gets the same treatment as "every day" - a window of a year would find
    # nothing for the first and everything for the second.
    cursor = on_or_after
    for _ in range(512):
        scheduled = next_occurrence(reminder, cursor)
        if scheduled is None:
            break
        if best is not None and best.date <= scheduled:
            # Nothing further along the schedule can beat what we already have.
            break
        record = overrides.get(scheduled)
        if record is None or not record.is_done:
            candidate = build(scheduled)
            # A snooze can push an instance past later ones; it is still a
            # candidate, but not necessarily the winner.
            if candidate.date >= on_or_after and (best is None or candidate.date < best.date):
                best = candidate
            if not candidate.snoozed:
                break
        cursor = scheduled + timedelta(days=1)

    return best
