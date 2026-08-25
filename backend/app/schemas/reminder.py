import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.reminder import Recurrence, ReminderType
from app.schemas.animal import AnimalRead
from app.schemas.common import UTCDateTime


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    reminder_type: ReminderType
    due_date: date
    recurrence: Recurrence = Recurrence.NONE
    # Bounded at both ends. Below 1 every occurrence generator would loop on
    # the same date forever; the upper bound is arbitrary but keeps "every
    # 4000 weeks" out of a scheduler that walks occurrences one at a time.
    recurrence_interval: int = Field(default=1, ge=1, le=365)
    repeat_until: date | None = None
    #: How many days ahead to announce THIS one. None means the account default.
    notify_lead_days: int | None = Field(default=None, ge=0, le=90)
    notes: str | None = None
    animal_id: uuid.UUID


class ReminderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    reminder_type: ReminderType | None = None
    due_date: date | None = None
    recurrence: Recurrence | None = None
    recurrence_interval: int | None = Field(default=None, ge=1, le=365)
    repeat_until: date | None = None
    notify_lead_days: int | None = Field(default=None, ge=0, le=90)
    notes: str | None = None
    animal_id: uuid.UUID | None = None


class OccurrenceSnooze(BaseModel):
    """Push one instance back, without touching the series.

    Either a number of days from where it currently sits, or an outright date.
    Days is what the buttons send, because "3 days" is the thought somebody
    actually has; the date is there for the ones who want a specific day.
    """

    days: int | None = Field(default=None, ge=1, le=365)
    until: date | None = None


class ReminderOccurrenceRead(BaseModel):
    """One dated instance, as the calendar draws it."""

    reminder_id: uuid.UUID
    #: What the recurrence rule produced. The identity used by every endpoint.
    scheduled_date: date
    #: Where it actually lands - the same, unless it was snoozed.
    date: date
    done: bool
    snoozed: bool


class ReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    reminder_type: ReminderType
    due_date: date
    recurrence: Recurrence
    recurrence_interval: int
    repeat_until: date | None
    notify_lead_days: int | None = None
    #: The next date this falls on that has NOT been done, computed
    #: server-side. Snoozes move it; completions skip past it.
    next_occurrence: date | None = None
    #: The scheduled date behind `next_occurrence`, which is what the complete
    #: and snooze endpoints are keyed on. They differ when it was snoozed.
    next_scheduled_date: date | None = None
    #: Whether that next one has been pushed back from where the rule put it.
    next_is_snoozed: bool = False
    #: The rule in words - "every 3 months, until 01 Dec 2026".
    recurrence_description: str = "does not repeat"
    #: How many instances have been ticked off. A one-off reads as finished
    #: when this is 1; a repeating one just has history.
    completed_count: int = 0
    #: The most recently ticked-off instance, by its scheduled date.
    #:
    #: Sent rather than left for the client to work out. "Undo the last tick"
    #: needs a specific date, and the only way to get one in the browser would
    #: be to reconstruct it from the recurrence rule - which is the arithmetic
    #: that was just taken out of the calendar for being a second, drifting
    #: implementation of this module.
    last_completed_date: date | None = None
    #: True when there is nothing left to do: a one-off that has been done, or
    #: a repeating one that has run past its end date. These leave the default
    #: view - a calendar of things already dealt with is the clutter.
    is_finished: bool = False
    notes: str | None
    animal_id: uuid.UUID
    owner_id: uuid.UUID
    created_at: UTCDateTime
    animal: AnimalRead


class DuplicateGroup(BaseModel):
    """Several reminders that say exactly the same thing.

    `keep_id` is the oldest, which is the one with the history attached - its
    completions, and whatever an appointment confirmation put in its notes.
    The copies are the ones made afterwards.
    """

    title: str
    reminder_type: ReminderType
    due_date: date
    animal_id: uuid.UUID
    animal_name: str
    keep_id: uuid.UUID
    duplicate_ids: list[uuid.UUID]
    reminders: list[ReminderRead]


class DuplicateResolution(BaseModel):
    """Which extra copies to delete.

    Explicit ids rather than "delete all duplicates", so the interface has to
    show somebody exactly what is about to go and a stale page cannot delete a
    reminder that was created since it loaded.
    """

    delete_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
