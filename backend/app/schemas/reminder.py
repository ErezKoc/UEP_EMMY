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
    notes: str | None = None
    animal_id: uuid.UUID


class ReminderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    reminder_type: ReminderType | None = None
    due_date: date | None = None
    recurrence: Recurrence | None = None
    notes: str | None = None
    animal_id: uuid.UUID | None = None


class ReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    reminder_type: ReminderType
    due_date: date
    recurrence: Recurrence
    recurrence_interval: int
    repeat_until: date | None
    #: The next date this falls on, computed server-side. The calendar can work
    #: it out too, but a notification email cannot, and both must agree.
    next_occurrence: date | None = None
    #: The rule in words - "every 3 months, until 01 Dec 2026".
    recurrence_description: str = "does not repeat"
    notes: str | None
    animal_id: uuid.UUID
    owner_id: uuid.UUID
    created_at: UTCDateTime
    animal: AnimalRead
