import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.animal import AgeCategory
from app.schemas.common import UTCDateTime


class AnimalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    species: str = Field(min_length=1, max_length=80)
    breed: str | None = Field(default=None, max_length=120)
    age_category: AgeCategory = AgeCategory.UNKNOWN
    owner_id: uuid.UUID


class AnimalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    species: str
    breed: str | None
    age_category: AgeCategory
    owner_id: uuid.UUID
    created_at: UTCDateTime
