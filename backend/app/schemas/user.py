import uuid
from datetime import date, time
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

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
    clinic_hours_grid: dict | None = None
    clinic_timezone: str | None = None
    clinic_latitude: float | None = None
    clinic_longitude: float | None = None
    specialties: list[str] = Field(default_factory=list)
    consultation_fee_min: float | None = None
    consultation_fee_max: float | None = None
    fee_currency: str | None = None
    notify_in_app: bool = True
    notify_email: bool = True
    notify_lead_days: int = 1
    notify_time: time = time(9, 0)
    notify_timezone: str | None = None
    verification_status: VerificationStatus
    # Convenience flag so clients never re-derive "vet AND verified".
    is_verified_vet: bool

    @field_validator("specialties", mode="before")
    @classmethod
    def no_specialties_is_an_empty_list(cls, value: object) -> object:
        return [] if value is None else value
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
    #: The machine-readable grid behind `open_now`. Sent so a profile page can
    #: show the week it is actually filtering on, rather than asking the reader
    #: to trust a badge.
    clinic_hours_grid: dict | None = None
    clinic_timezone: str | None = None
    clinic_latitude: float | None = None
    clinic_longitude: float | None = None
    specialties: list[str] = Field(default_factory=list)
    #: The same list in words, so a client never has to hold its own copy of
    #: the catalogue and drift from it.
    specialty_labels: list[str] = Field(default_factory=list)
    consultation_fee_min: float | None = None
    consultation_fee_max: float | None = None
    fee_currency: str | None = None
    accepts_appointments: bool = False
    verification_status: VerificationStatus
    is_verified_vet: bool

    # ------------------------------- worked out per request, not stored on the row
    #: Straight-line kilometres from the point the caller gave, or None when
    #: either end has no coordinates. "None" means unknown, never "far".
    distance_km: float | None = None
    #: True, False, or None for "this practice has published no opening grid".
    #: The third case is the important one: a clinic nobody has entered hours
    #: for is not a closed clinic, and a boolean cannot say that.
    open_now: bool | None = None
    #: "18:00" when open, so the card can say how long is left.
    closes_at: str | None = None
    #: When it next opens, and on which day, when closed.
    opens_at: str | None = None
    opens_day: str | None = None
    #: The soonest opening this practice has PUBLISHED HERE, if any. Not a view
    #: of their diary - see the availability model.
    next_slot_date: date | None = None
    next_slot_time: time | None = None
    published_slot_count: int = 0

    @field_validator("specialties", mode="before")
    @classmethod
    def no_specialties_is_an_empty_list(cls, value: object) -> object:
        """A NULL column reads as "none chosen", not as a missing field.

        The column is nullable, so every practice that predates specialties
        hands this validator `None` - and a list field given None fails
        validation, which took out every endpoint that embeds a vet profile,
        appointments included.
        """
        return [] if value is None else value


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
    #: The optional grid behind "open now". Malformed days are dropped rather
    #: than refused - this is decoration on top of the sentence above, and
    #: failing the whole save over a bad Tuesday would cost the practice its
    #: phone-number edit too.
    clinic_hours_grid: dict | None = None
    clinic_timezone: str | None = Field(default=None, max_length=64)
    clinic_latitude: float | None = Field(default=None, ge=-90, le=90)
    clinic_longitude: float | None = Field(default=None, ge=-180, le=180)
    specialties: list[str] | None = None
    #: Bounded well above any real consultation fee. The ceiling is not a
    #: judgement about pricing - it is there so a stray keypress cannot put a
    #: nine-digit number on a public profile.
    consultation_fee_min: float | None = Field(default=None, ge=0, le=1_000_000)
    consultation_fee_max: float | None = Field(default=None, ge=0, le=1_000_000)
    fee_currency: str | None = Field(default=None, max_length=8)
    accepts_appointments: bool | None = None
    notify_in_app: bool | None = None
    notify_email: bool | None = None
    # Capped rather than unbounded: an alert 200 days before a booster is not a
    # reminder, it is noise, and the scheduler would announce it every day.
    notify_lead_days: int | None = Field(default=None, ge=0, le=30)
    #: What time of day alerts go out, on the reader's own clock.
    notify_time: time | None = None
    #: An IANA zone name ("Europe/Istanbul"). Validated rather than stored as
    #: typed: an unknown zone would silently fall back to UTC in the scheduler,
    #: and the settings page would keep showing the value the person chose - so
    #: they would believe a preference was honoured that never was.
    notify_timezone: str | None = Field(default=None, max_length=64)

    @field_validator("notify_timezone")
    @classmethod
    def a_zone_the_platform_knows(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned not in available_timezones():
            raise ValueError(f"{cleaned!r} is not a timezone this server recognises.")
        return cleaned


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
