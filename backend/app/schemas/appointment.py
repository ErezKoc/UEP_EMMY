"""What an owner asks for, and what a practice answers."""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.appointment import AppointmentStatus
from app.schemas.animal import AnimalRead
from app.schemas.common import UTCDateTime
from app.schemas.user import UserSummary, VeterinarianRead


class AppointmentCreate(BaseModel):
    vet_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=1000)
    preferred_date: date
    preferred_time_note: str | None = Field(default=None, max_length=120)
    animal_id: uuid.UUID | None = None


class AppointmentDecision(BaseModel):
    """The practice's reply.

    `scheduled_date` is optional on a confirmation and defaults to the day the
    owner asked for; supplying a different one is how a practice offers another
    time. It is ignored on a decline, where the only useful field is the note.
    """

    confirm: bool
    scheduled_date: date | None = None
    vet_note: str | None = Field(default=None, max_length=1000)


class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: AppointmentStatus
    reason: str
    preferred_date: date
    preferred_time_note: str | None
    scheduled_date: date | None
    vet_note: str | None
    created_at: UTCDateTime
    responded_at: UTCDateTime | None
    #: Both sides are always sent. The owner needs the practice's contact
    #: details on their own list, and the practice needs to know who is asking
    #: without a second request per row.
    owner: UserSummary
    vet: VeterinarianRead
    animal: AnimalRead | None = None
    #: Set when a confirmation put this on the owner's calendar. Null when the
    #: request named no pet, because a reminder belongs to one.
    reminder_id: uuid.UUID | None = None
