import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, String, Uuid
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
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(
            VerificationStatus,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=VerificationStatus.UNVERIFIED,
        index=True,
    )
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
