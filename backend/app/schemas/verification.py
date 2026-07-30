import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import VerificationStatus
from app.schemas.common import UTCDateTime
from app.schemas.user import VeterinarianRead


class VetVerificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: VerificationStatus
    document_url: str
    license_number: str | None
    review_note: str | None
    created_at: UTCDateTime
    reviewed_at: UTCDateTime | None
    reviewed_by_name: str | None
    # Who submitted it — the admin queue needs the vet's public profile.
    user: VeterinarianRead


class VerificationDecision(BaseModel):
    """Admin review outcome. Only `verified` or `rejected` are accepted."""

    status: VerificationStatus
    review_note: str | None = Field(default=None, max_length=1000)
