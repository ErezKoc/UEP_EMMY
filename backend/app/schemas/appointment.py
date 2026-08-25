"""What an owner asks for, and what a practice answers."""

import uuid
from datetime import date, time

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.appointment import AppointmentStatus
from app.schemas.animal import AnimalRead
from app.schemas.common import UTCDateTime
from app.schemas.user import UserSummary, VeterinarianRead


class AppointmentCreate(BaseModel):
    vet_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=1000)
    preferred_date: date
    #: Optional: "any time that day" is a real answer and the commonest one.
    preferred_time: time | None = None
    preferred_time_note: str | None = Field(default=None, max_length=120)
    animal_id: uuid.UUID | None = None
    #: A published opening the owner picked, instead of naming their own time.
    #: When set, the date and time are taken from the slot.
    slot_id: uuid.UUID | None = None


class AppointmentDecision(BaseModel):
    """The practice's reply.

    `scheduled_date` is optional on a confirmation and defaults to the day the
    owner asked for; supplying a different one is how a practice offers another
    time. Both are ignored on a decline, where the only useful field is the
    note.

    `scheduled_time` is NOT optional on a confirmation, and that is the point of
    it. A practice holds its own diary and is the only party that knows when the
    slot is; an owner told "confirmed for 12 September" has been given a day and
    still has to telephone to find out the one thing they needed. The validator
    below refuses the confirmation rather than storing a booking with no time,
    because a half-answered confirmation is indistinguishable from a complete
    one once it is in the database.
    """

    confirm: bool
    scheduled_date: date | None = None
    scheduled_time: time | None = None
    vet_note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def a_confirmation_names_a_time(self) -> "AppointmentDecision":
        if self.confirm and self.scheduled_time is None:
            raise ValueError(
                "Give the exact time you are confirming - an appointment with "
                "only a date leaves the owner not knowing when to arrive."
            )
        return self


class AppointmentReschedule(BaseModel):
    """A proposal to move an appointment both sides already agreed to.

    Either side may send one. The practice needs it because clinics run late,
    lists get rearranged and vets get called out; the owner needs it because
    the alternative on offer until now was cancelling outright and starting
    again from an empty form, which loses the reason, the pet, the history and
    the practice's place in the queue.
    """

    new_date: date
    new_time: time
    note: str | None = Field(default=None, max_length=1000)


class RescheduleDecision(BaseModel):
    """The other side's answer to a proposed move."""

    accept: bool
    note: str | None = Field(default=None, max_length=1000)


class AppointmentMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class AppointmentMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    body: str
    sender: UserSummary
    created_at: UTCDateTime
    read_at: UTCDateTime | None = None


class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: AppointmentStatus
    reason: str
    preferred_date: date
    preferred_time: time | None
    preferred_time_note: str | None
    scheduled_date: date | None
    scheduled_time: time | None
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

    # ------------------------------------------------- a move under discussion
    proposed_date: date | None = None
    proposed_time: time | None = None
    proposed_note: str | None = None
    #: Who proposed it. The client needs this to decide whether to show
    #: "waiting for them" or the Accept and Decline buttons - only the side
    #: that did NOT propose may answer.
    proposed_by_id: uuid.UUID | None = None

    # ------------------------------------------------------------- the thread
    #: The published opening this was requested against, if any.
    slot_id: uuid.UUID | None = None
    message_count: int = 0
    #: Unread BY THE VIEWER, so it cannot be read off the row alone - the
    #: appointments endpoint fills it in per caller, the way the community feed
    #: does for "you found this helpful".
    unread_message_count: int = 0
