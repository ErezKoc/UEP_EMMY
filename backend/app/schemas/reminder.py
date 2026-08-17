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
    notes: str | None
    animal_id: uuid.UUID
    owner_id: uuid.UUID
    created_at: UTCDateTime
    animal: AnimalRead
