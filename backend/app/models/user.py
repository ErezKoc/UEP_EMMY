import enum
import uuid
from datetime import datetime, time, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Float, Integer, String, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import PortableJSON

if TYPE_CHECKING:
    from app.models.animal import Animal
    from app.models.post import Comment, Post
    from app.models.verification import VetVerification


class UserRole(str, enum.Enum):
    OWNER = "owner"
    VETERINARIAN = "veterinarian"
    # Reviews veterinarian credentials. Created by seeding, never via signup.
    ADMIN = "admin"


class AccountStatus(str, enum.Enum):
    """Moderation state of an account, set by an administrator via a report.

    `SUSPENDED` is temporary (see `User.suspended_until`) and lapses on its own;
    `BANNED` is indefinite and also blocks signing in. Both are reversible by
    reinstating the account.
    """

    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"


class VerificationStatus(str, enum.Enum):
    """Credential state of a veterinarian account (meaningless for owners).

    Denormalized onto `User` so every post/comment can show a trustworthy badge
    without joining the verification table; `VetVerification` keeps the history.
    """

    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # PBKDF2 hash (see core/security.py). Nullable so pre-auth rows keep working;
    # such accounts simply cannot log in.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120))
    bio: Mapped[str | None] = mapped_column(String(1000))
    avatar_url: Mapped[str | None] = mapped_column(String(1024))
    # native_enum=False stores the value as a VARCHAR + CHECK constraint, which
    # keeps the schema portable and avoids ALTER TYPE migrations on Postgres.
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        default=UserRole.OWNER,
        index=True,
    )
    # Veterinarian-specific profile fields; NULL for pet owners.
    clinic_name: Mapped[str | None] = mapped_column(String(255))
    license_number: Mapped[str | None] = mapped_column(String(64))
    # How to reach the practice. The directory listed names and biographies and
    # no way to contact anybody, so "find a vet" found you a person and then
    # left you to search for their phone number somewhere else.
    #
    # All free text and all optional. Nothing here is validated into a format:
    # phone numbers, addresses and opening hours differ by country, and a
    # regular expression written against one of them silently locks out the
    # rest. What the columns buy is that the details exist at all.
    clinic_phone: Mapped[str | None] = mapped_column(String(40))
    #: Out of hours. Kept apart from the line above rather than folded into
    #: "phone", because the moment an owner needs it is the moment they cannot
    #: afford to try the wrong number first.
    clinic_emergency_phone: Mapped[str | None] = mapped_column(String(40))
    clinic_email: Mapped[str | None] = mapped_column(String(255))
    clinic_website: Mapped[str | None] = mapped_column(String(1024))
    clinic_address_line: Mapped[str | None] = mapped_column(String(255))
    clinic_city: Mapped[str | None] = mapped_column(String(120))
    clinic_postcode: Mapped[str | None] = mapped_column(String(20))
    clinic_country: Mapped[str | None] = mapped_column(String(120))
    #: Free text ("Mon-Fri 9-6, Sat 9-1"). A structured weekly schedule was the
    #: obvious alternative and it cannot express half the practices we would be
    #: asking to fill it in — split hours, alternate Saturdays, seasonal
    #: closures. A practice writing its own sentence is more accurate than a
    #: grid that quietly rounds it off.
    clinic_hours: Mapped[str | None] = mapped_column(String(500))
    #: The same opening hours as a machine-readable weekly grid, for filtering.
    #:
    #: ADDED BESIDE the sentence above, never replacing it, and the reason is
    #: the comment above: a grid cannot express alternate Saturdays or a
    #: seasonal closure, so the practice's own sentence stays the thing a human
    #: reads. This exists only so "open now" is a question the directory can
    #: answer at all, and it is optional - a practice that skips it keeps its
    #: sentence and is reported as "hours not listed", never as closed.
    #:
    #: Shape: {"mon": [["09:00","13:00"], ["14:00","18:00"]], ...}. A list per
    #: day because split hours are the norm, and a single pair would tell
    #: somebody with an emergency at 13:30 to set off.
    clinic_hours_grid: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)
    #: The IANA zone the grid is read in. Without it "open until 18:00" is
    #: evaluated wherever the server happens to live.
    clinic_timezone: Mapped[str | None] = mapped_column(String(64))

    #: Where the practice is, for distance. Latitude and longitude rather than
    #: a geocoded address, because geocoding needs a service this deployment
    #: does not have - and a wrong pin is worse than no pin, so the practice
    #: sets its own.
    clinic_latitude: Mapped[float | None] = mapped_column(Float)
    clinic_longitude: Mapped[float | None] = mapped_column(Float)

    #: What this practice treats, as slugs from `SPECIALTIES`. A fixed list
    #: rather than free text because it is a filter - see the catalogue.
    specialties: Mapped[list | None] = mapped_column(PortableJSON, nullable=True)

    #: What a standard consultation costs, as a range.
    #:
    #: A range, not a price, because a consultation is not one price and a
    #: single figure would be either the cheapest thing they do or a number
    #: nobody is ever charged. Both ends optional: a practice willing to say
    #: "from 400" should not have to invent a ceiling.
    consultation_fee_min: Mapped[float | None] = mapped_column(Float)
    consultation_fee_max: Mapped[float | None] = mapped_column(Float)
    #: ISO code. Stored per practice, because this directory has clinics in
    #: more than one country and an unlabelled "400" is not a price.
    fee_currency: Mapped[str | None] = mapped_column(String(8))

    #: Whether this practice takes appointment requests through the platform.
    #: Opt-in: a request sent to a practice that is not watching for one is
    #: worse than no button, because the owner believes they have asked.
    accepts_appointments: Mapped[bool] = mapped_column(Boolean, default=False)

    # How this person wants to hear from us. Both default ON: somebody who set
    # a reminder asked to be reminded, and defaulting to silence would make the
    # feature look broken to everyone who never found the settings page.
    notify_in_app: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    notify_email: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    #: How many days ahead a reminder is announced. 0 means "on the day".
    #: A per-reminder override lives on the reminder itself; this is the
    #: fallback for everything that has not asked for something different.
    notify_lead_days: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    #: What time of day to send them.
    #:
    #: The sweep runs every few minutes and used to announce whenever it next
    #: happened to wake up, which for anybody with email on meant a message at
    #: 03:14. Nobody acts on a reminder at 03:14; they wake up to it already
    #: read and it is gone.
    notify_time: Mapped[time] = mapped_column(
        Time, default=time(9, 0), server_default="09:00:00"
    )
    #: The IANA zone that time is in ("Europe/Istanbul"), or NULL for UTC.
    #:
    #: Stored rather than inferred, because a time of day is meaningless
    #: without one: 09:00 on a server in UTC is the middle of the night for
    #: half the people using it. The browser knows its own zone and offers it;
    #: NULL falls back to UTC and the settings page says so rather than
    #: pretending a preference was honoured.
    notify_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Extra lead times, as a list of whole days: `[7, 1, 0]` announces a week
    #: ahead, the day before, and on the day.
    #:
    #: One lead time was not enough for the thing people actually want from a
    #: reminder. A booster needs a warning early enough to get an appointment
    #: AND a nudge the night before, and a single number can only be one of
    #: those. Each lead is announced separately and keyed separately, so none
    #: of them silences the others.
    #:
    #: NULL means "just `notify_lead_days`", which is what every existing
    #: account meant before this column existed - so nobody's alerts change
    #: until they ask for something different.
    notify_leads: Mapped[list | None] = mapped_column(PortableJSON, nullable=True)

    #: When this address was proved by clicking a link sent to it, or NULL for
    #: an address nobody has confirmed.
    #:
    #: Nothing is gated on it today: an unverified account can still use the
    #: platform, because locking a pet owner out of their own reminders over an
    #: unread email would cost more than it protects. It is recorded so the
    #: account page can say which state the address is in, and so a future
    #: gate has something true to read.
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: An address the account has asked to move to, not yet proved.
    #:
    #: The new address does NOT replace `email` until its link is clicked. A
    #: typo in this field would otherwise send every future password reset to
    #: an address the owner cannot read, and the account is then unrecoverable
    #: by exactly the mechanism meant to recover it.
    pending_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(
            VerificationStatus,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=VerificationStatus.UNVERIFIED,
        index=True,
    )
    account_status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        default=AccountStatus.ACTIVE,
        index=True,
    )
    # When a suspension lapses. NULL alongside SUSPENDED means indefinite.
    suspended_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Shown to the member themselves so a suspension is never unexplained.
    moderation_note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    #: Openings this practice has published on the platform. Empty for an
    #: owner account, and empty for a practice that has published none -
    #: which the directory reports as "no times published", not as full.
    availability_slots: Mapped[list["AvailabilitySlot"]] = relationship(
        "AvailabilitySlot", back_populates="vet", cascade="all, delete-orphan"
    )
    animals: Mapped[list["Animal"]] = relationship(back_populates="owner")
    posts: Mapped[list["Post"]] = relationship(back_populates="author")
    comments: Mapped[list["Comment"]] = relationship(back_populates="author")
    verifications: Mapped[list["VetVerification"]] = relationship(
        back_populates="user",
        foreign_keys="VetVerification.user_id",
        cascade="all, delete-orphan",
        order_by="VetVerification.created_at.desc()",
    )

    @property
    def email_is_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def lead_days(self) -> list[int]:
        """Every lead time this account wants, largest first and de-duplicated.

        Falls back to the single `notify_lead_days` when `notify_leads` is
        unset or unusable, which is what an account that predates the column
        already meant. Values are clamped to the range the settings form
        allows, so a hand-edited row cannot make the scheduler announce a
        reminder two hundred days early on every sweep.
        """
        raw = self.notify_leads if isinstance(self.notify_leads, list) else None
        if not raw:
            return [max(0, self.notify_lead_days or 0)]
        cleaned = set()
        for value in raw:
            if isinstance(value, bool) or not isinstance(value, int):
                continue
            cleaned.add(min(30, max(0, value)))
        return sorted(cleaned, reverse=True) or [max(0, self.notify_lead_days or 0)]

    @property
    def is_verified_vet(self) -> bool:
        return (
            self.role == UserRole.VETERINARIAN
            and self.verification_status == VerificationStatus.VERIFIED
        )

    @property
    def is_banned(self) -> bool:
        return self.account_status == AccountStatus.BANNED

    @property
    def is_suspended(self) -> bool:
        """True only while a suspension is still running (it lapses on its own)."""
        if self.account_status != AccountStatus.SUSPENDED:
            return False
        if self.suspended_until is None:
            return True
        # SQLite drops tzinfo on round-trip, so normalise before comparing.
        until = self.suspended_until
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        return until > datetime.now(timezone.utc)

    @property
    def can_participate(self) -> bool:
        """May this account write posts, comments, and reports right now?"""
        return not self.is_banned and not self.is_suspended
