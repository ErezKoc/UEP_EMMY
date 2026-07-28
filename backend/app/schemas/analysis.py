import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.animal import AgeCategory
from app.schemas.animal import AnimalRead
from app.schemas.common import UTCDateTime


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


class AnalysisHistoryItem(BaseModel):
    """One row of the signed-in user's analysis history (GET /v1/analysis)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    image_url: str
    created_at: UTCDateTime
    # Stored verbatim as JSON at upload time; validates back into the schema.
    result: AnalysisResult
    # The linked pet, if any (deleted pets leave analyses unlinked).
    animal: AnimalRead | None
