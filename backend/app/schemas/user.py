import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import AccountStatus, UserRole, VerificationStatus
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
    verification_status: VerificationStatus
    # Convenience flag so clients never re-derive "vet AND verified".
    is_verified_vet: bool
    account_status: AccountStatus
    created_at: UTCDateTime


class CurrentUserRead(UserRead):
    """The signed-in user's own account, including why it is restricted.

    The moderator's note and suspension end date are only ever returned to the
    account they concern — never on a public author profile.
    """

    suspended_until: UTCDateTime | None = None
    moderation_note: str | None = None
    can_participate: bool


class UserSummary(BaseModel):
    """Compact identity for moderation views (no private account fields)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    role: UserRole
    avatar_url: str | None = None
    is_verified_vet: bool


class ReportedUserRead(UserSummary):
    """A reported member, with the moderation state an administrator needs."""

    email: str
    clinic_name: str | None = None
    license_number: str | None = None
    verification_status: VerificationStatus
    account_status: AccountStatus
    suspended_until: UTCDateTime | None = None
    created_at: UTCDateTime


class VeterinarianRead(BaseModel):
    """Public veterinarian profile; private account fields stay private."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    role: UserRole
    bio: str | None = None
    avatar_url: str | None = None
    clinic_name: str | None = None
    license_number: str | None = None
    verification_status: VerificationStatus
    is_verified_vet: bool


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
