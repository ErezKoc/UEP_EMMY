"""The dashboard, as one response."""

import uuid
from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.animal import AnimalRead


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str
    #: Consequence, not loudness. "urgent" means an animal may need seeing or
    #: an appointment may be lost; "soon" has a deadline; "info" is worth
    #: knowing. A dashboard where everything shouts is one nobody reads.
    severity: Literal["urgent", "soon", "info"]
    title: str
    detail: str
    link: str
    pet_name: str | None = None
    due: date | None = None


class AppointmentBrief(BaseModel):
    """Just enough of an appointment to put it on a card."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scheduled_date: date | None = None
    scheduled_time: time | None = None
    practice: str
    pet_name: str | None = None
    #: True while a suggested move is waiting on somebody, so a card can say
    #: the date may still change rather than presenting it as settled.
    move_pending: bool = False


class PetSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    animal: AnimalRead
    overdue_reminders: int = 0
    next_reminder_title: str | None = None
    next_reminder_date: date | None = None
    next_appointment: AppointmentBrief | None = None
    #: The newest symptom check for this pet. `level` is kept as a plain string
    #: rather than an enum: stored verdicts are reproduced verbatim, and a level
    #: this build does not recognise must render as unknown rather than 500 the
    #: whole page.
    last_check_level: str | None = None
    last_check_headline: str | None = None
    last_check_at: date | None = None
    last_analysis_at: date | None = None
    profile_conflicts: int = 0
    tasks: list[TaskRead] = []


class DashboardRead(BaseModel):
    pets: list[PetSummaryRead]
    #: Every task, across every pet, already ranked. Sorted once on the server
    #: so this page and any other agree about what matters most.
    tasks: list[TaskRead]
    next_appointment: AppointmentBrief | None = None
    urgent_count: int = 0
