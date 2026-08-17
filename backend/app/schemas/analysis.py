import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.animal import AgeCategory
from app.schemas.animal import AnimalRead
from app.schemas.common import UTCDateTime
from app.schemas.triage import SymptomIntake, TriageAssessment


class BreedCandidate(BaseModel):
    breed: str
    confidence: float = Field(ge=0.0, le=1.0)


class AgeEstimate(BaseModel):
    category: AgeCategory
    min_years: float
    max_years: float
    confidence: float = Field(ge=0.0, le=1.0)


class AnalysisResult(BaseModel):
    """Structured output of the image-analysis service.

    This is the contract the real AWS Rekognition/SageMaker adapter must also
    produce, so the rest of the platform never changes when the mock is swapped.
    """

    model_version: str
    species: str
    species_confidence: float = Field(ge=0.0, le=1.0)
    breed_candidates: list[BreedCandidate]
    age_estimate: AgeEstimate
    characteristics: list[str]


class AnalysisResponse(BaseModel):
    analysis_id: uuid.UUID
    animal_id: uuid.UUID | None
    image_url: str
    created_at: UTCDateTime
    result: AnalysisResult
    # Present only when the owner answered the symptom questions.
    triage: TriageAssessment | None = None


class AnalysisHistoryItem(BaseModel):
    """One row of the signed-in user's analysis history (GET /v1/analysis)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    image_url: str
    created_at: UTCDateTime
    # Stored verbatim as JSON at upload time; validates back into the schema.
    result: AnalysisResult
    triage: TriageAssessment | None = None
    # The linked pet, if any (deleted pets leave analyses unlinked).
    animal: AnimalRead | None

    @field_validator("triage", mode="before")
    @classmethod
    def drop_unreadable_triage(cls, value: Any) -> Any:
        """Never let one old stored verdict break the whole history page.

        Triage results are stored verbatim so a past verdict stays reproducible
        after the rules change. The cost is that an old snapshot may not match
        today's schema — when the rule table was reorganised, `fired_rules`
        gained `sources` in place of `citation`. Validating those strictly made
        a single legacy row return 500 for the entire list, which is a far worse
        outcome than showing that row without its triage.
        """
        if value is None or isinstance(value, TriageAssessment):
            return value
        try:
            return TriageAssessment.model_validate(value)
        except Exception:
            return None


class AnalysisDetail(AnalysisHistoryItem):
    """Complete stored analysis, including the owner's symptom answers."""

    intake: SymptomIntake | None = None

    @field_validator("intake", mode="before")
    @classmethod
    def drop_unreadable_intake(cls, value: Any) -> Any:
        if value is None or isinstance(value, SymptomIntake):
            return value
        try:
            return SymptomIntake.model_validate(value)
        except Exception:
            return None
