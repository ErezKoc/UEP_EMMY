import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.animal import AgeCategory
from app.schemas.common import UTCDateTime


class _BirthDateValidatorMixin(BaseModel):
    @field_validator("birth_date", check_fields=False)
    @classmethod
    def birth_date_not_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Birth date cannot be in the future.")
        return value


class AnimalCreate(_BirthDateValidatorMixin):
    """New pet; the owner is always the authenticated user, never the payload."""

    name: str = Field(min_length=1, max_length=120)
    species: str = Field(min_length=1, max_length=80)
    breed: str | None = Field(default=None, max_length=120)
    birth_date: date | None = None
    age_category: AgeCategory | None = None


class AnimalUpdate(_BirthDateValidatorMixin):
    """Partial update; only provided fields change."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    species: str | None = Field(default=None, min_length=1, max_length=80)
    breed: str | None = Field(default=None, max_length=120)
    birth_date: date | None = None
    age_category: AgeCategory | None = None
    photo_position_x: int = Field(default=50, ge=0, le=100)
    photo_position_y: int = Field(default=50, ge=0, le=100)
    photo_zoom: float = Field(default=1.0, ge=1.0, le=3.0)


class AnimalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    species: str
    breed: str | None
    birth_date: date | None
    photo_url: str | None
    photo_position_x: int
    photo_position_y: int
    photo_zoom: float
    age_category: AgeCategory
    owner_id: uuid.UUID
    created_at: UTCDateTime
