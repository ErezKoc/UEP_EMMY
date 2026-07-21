import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole
from app.schemas.common import UTCDateTime


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    role: UserRole
    bio: str | None = None
    avatar_url: str | None = None
    clinic_name: str | None = None
    license_number: str | None = None
    created_at: UTCDateTime


class UserUpdate(BaseModel):
    """Partial profile update; only provided fields change."""

    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    bio: str | None = Field(default=None, max_length=1000)
    email: EmailStr | None = None
    clinic_name: str | None = Field(default=None, max_length=255)
    license_number: str | None = Field(default=None, max_length=64)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
