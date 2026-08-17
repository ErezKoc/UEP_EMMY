"""A saved symptom check, as the history and detail views read it."""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.animal import AgeCategory
from app.schemas.animal import AnimalRead
from app.schemas.common import UTCDateTime
from app.schemas.triage import SymptomIntake, TriageAssessment


class SymptomCheckCreate(SymptomIntake):
    """The intake, plus the pet it is about.

    `SymptomIntake` itself stays pet-agnostic because the photo-upload path
    already carries `animal_id` as its own multipart field; only this JSON
    endpoint needs the two combined.
    """

    animal_id: uuid.UUID | None = None


class SymptomCheckRead(BaseModel):
    """One stored check, with the owner's answers and the engine's verdict."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: UTCDateTime
    species: str | None = None
    age_category: AgeCategory | None = None
    intake: SymptomIntake | None = None
    triage: TriageAssessment | None = None
    # The linked pet, if any (deleting a pet leaves its checks unlinked).
    animal: AnimalRead | None = None

    @field_validator("triage", mode="before")
    @classmethod
    def drop_unreadable_triage(cls, value: Any) -> Any:
        """Never let one old stored verdict break the whole history page.

        Same reasoning as `AnalysisHistoryItem`: verdicts are stored verbatim so
        they stay reproducible, which means an old snapshot may no longer match
        today's schema. Showing that row without its verdict beats returning 500
        for the entire list.
        """
        if value is None or isinstance(value, TriageAssessment):
            return value
        try:
            return TriageAssessment.model_validate(value)
        except Exception:
            return None

    @field_validator("intake", mode="before")
    @classmethod
    def drop_unreadable_intake(cls, value: Any) -> Any:
        if value is None or isinstance(value, SymptomIntake):
            return value
        try:
            return SymptomIntake.model_validate(value)
        except Exception:
            return None
