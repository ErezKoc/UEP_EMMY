"""Openings a practice publishes, and what an owner sees of them."""

import uuid
from datetime import date, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SlotCreate(BaseModel):
    """One opening, or a run of them.

    `repeat_weeks` exists because publishing availability one slot at a time is
    the reason nobody would ever do it. A practice with a Tuesday-morning
    surgery is describing the same hour for the next two months, and asking
    them to enter it eight times is asking them not to bother.
    """

    slot_date: date
    start_time: time
    end_time: time
    capacity: int = Field(default=1, ge=1, le=50)
    note: str | None = Field(default=None, max_length=200)
    #: Repeat weekly for this many additional weeks. 0 publishes one slot.
    repeat_weeks: int = Field(default=0, ge=0, le=26)

    @model_validator(mode="after")
    def it_has_to_end_after_it_starts(self) -> "SlotCreate":
        if self.end_time <= self.start_time:
            raise ValueError("A slot has to end after it starts.")
        return self


class SlotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vet_id: uuid.UUID
    slot_date: date
    start_time: time
    end_time: time
    capacity: int
    note: str | None = None
    #: How many places are already confirmed. Sent alongside capacity rather
    #: than as a single "places left", so an open surgery reads as "2 of 6
    #: taken" instead of a bare number an owner cannot interpret.
    taken: int = 0
    is_open: bool = True
