import enum
import uuid
from datetime import datetime, time, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

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
