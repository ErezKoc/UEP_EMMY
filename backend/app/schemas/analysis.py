import uuid
from typing import Any, Literal

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


class AnalysisCorrection(BaseModel):
    """The owner's word on what the animal actually is.

    Every field optional and every field independently clearable: an owner who
    only wants to fix the breed should not have to restate the species, and one
    who corrected a field by mistake needs a way back to the model's value.
    Sending `null` for a field clears that correction; omitting it leaves it as
    it was.
    """

    species: str | None = Field(default=None, max_length=80)
    breed: str | None = Field(default=None, max_length=120)
    age_category: AgeCategory | None = None
    #: Why, in the owner's words. Shown with the correction so a veterinarian
    #: reading the record later can see the reasoning, not just the overwrite.
    note: str | None = Field(default=None, max_length=500)


class AnalysisUpdate(BaseModel):
    """A correction, a relink, or both.

    `animal_id` uses a sentinel-free convention: omitted means "leave the link
    alone", `null` means "unlink". Pydantic's `model_fields_set` tells the two
    apart, which a plain default cannot.
    """

    correction: AnalysisCorrection | None = None
    animal_id: uuid.UUID | None = None


class ProfileConflictRead(BaseModel):
    """One thing this analysis and the pet's profile do not agree about.

    Computed on every read, never stored. A stored conflict is a stale one the
    moment the owner edits the profile or corrects the analysis, and a warning
    that survives the fix teaches people to ignore warnings.
    """

    field: Literal["species", "breed", "age"]
    #: "high" is a disagreement that changes what other features do, or one too
    #: large to be a boundary case. "low" is worth a look, not a worry.
    severity: Literal["high", "low"]
    profile_says: str
    analysis_says: str
    message: str
    #: True when the analysis's side of the disagreement is the owner's own
    #: correction rather than the model's output.
    from_correction: bool = False


class AnalysisResponse(BaseModel):
    analysis_id: uuid.UUID
    animal_id: uuid.UUID | None
    image_url: str
    created_at: UTCDateTime
    result: AnalysisResult
    # Present only when the owner answered the symptom questions.
    triage: TriageAssessment | None = None
    #: Where this result contradicts the linked pet's profile. Empty when no
    #: pet is linked - there is nothing to contradict.
    conflicts: list[ProfileConflictRead] = Field(default_factory=list)


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
    # Present once an owner has corrected something. The client shows the
    # corrected value and keeps the model's original beside it.
    correction: AnalysisCorrection | None = None
    corrected_at: UTCDateTime | None = None
    #: Filled in by the endpoint, not read off the row: it depends on the pet's
    #: profile as it is right now, not as it was when the photo was uploaded.
    conflicts: list[ProfileConflictRead] = Field(default_factory=list)

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
