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
    # Carried on the account too, not only on the public directory entry: the
    # profile form reads these back after a save, and without them the fields
    # a veterinarian just filled in would come back empty.
    clinic_phone: str | None = None
    clinic_emergency_phone: str | None = None
    clinic_email: str | None = None
    clinic_website: str | None = None
    clinic_address_line: str | None = None
    clinic_city: str | None = None
    clinic_postcode: str | None = None
    clinic_country: str | None = None
    clinic_hours: str | None = None
    accepts_appointments: bool = False
    notify_in_app: bool = True
    notify_email: bool = True
    notify_lead_days: int = 1
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
    # Public on purpose: a practice's phone number and address are the details
    # it advertises. The account's own login email stays private — `clinic_email`
    # is a separate field the practice chooses to publish.
    clinic_phone: str | None = None
    clinic_emergency_phone: str | None = None
    clinic_email: str | None = None
    clinic_website: str | None = None
    clinic_address_line: str | None = None
    clinic_city: str | None = None
    clinic_postcode: str | None = None
    clinic_country: str | None = None
    clinic_hours: str | None = None
    accepts_appointments: bool = False
    verification_status: VerificationStatus
    is_verified_vet: bool


class UserUpdate(BaseModel):
    """Partial profile update; only provided fields change."""

    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    bio: str | None = Field(default=None, max_length=1000)
    email: EmailStr | None = None
    clinic_name: str | None = Field(default=None, max_length=255)
    license_number: str | None = Field(default=None, max_length=64)
    clinic_phone: str | None = Field(default=None, max_length=40)
    clinic_emergency_phone: str | None = Field(default=None, max_length=40)
    clinic_email: str | None = Field(default=None, max_length=255)
    clinic_website: str | None = Field(default=None, max_length=1024)
    clinic_address_line: str | None = Field(default=None, max_length=255)
    clinic_city: str | None = Field(default=None, max_length=120)
    clinic_postcode: str | None = Field(default=None, max_length=20)
    clinic_country: str | None = Field(default=None, max_length=120)
    clinic_hours: str | None = Field(default=None, max_length=500)
    accepts_appointments: bool | None = None
    notify_in_app: bool | None = None
    notify_email: bool | None = None
    # Capped rather than unbounded: an alert 200 days before a booster is not a
    # reminder, it is noise, and the scheduler would announce it every day.
    notify_lead_days: int | None = Field(default=None, ge=0, le=30)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
