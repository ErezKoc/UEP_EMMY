from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole
from app.schemas.user import CurrentUserRead


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    # Deliberately not `UserRole`: admin accounts must never be self-registered.
    role: Literal[UserRole.OWNER, UserRole.VETERINARIAN] = UserRole.OWNER
    # Veterinarian-only profile fields; ignored for pet owners.
    clinic_name: str | None = Field(default=None, max_length=255)
    license_number: str | None = Field(default=None, max_length=64)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    user: CurrentUserRead
