"""One-time, expiring tokens for the things email has to prove.

Three purposes, one table, because the rules are identical for all of them:
long random secret, hashed at rest, valid for a fixed window, usable exactly
once, and revoked in bulk when a newer one supersedes it.

Only the SHA-256 of the token is stored. The raw value exists in the email and
nowhere else, so a leaked database dump is not a set of working password-reset
links - which is the entire reason to hash it, given the token IS the
credential for the few minutes it lives.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TokenPurpose(str, enum.Enum):
    """What this token is allowed to do.

    Kept apart so a link that proves an address cannot also change a password.
    A single "auth token" would mean an email-verification link forwarded to a
    colleague is a password reset.
    """

    EMAIL_VERIFICATION = "email_verification"
    #: Proves a NEW address before it replaces the old one. Carries the address
    #: it is for in `new_email`; the account keeps the old one until this is used.
    EMAIL_CHANGE = "email_change"
    PASSWORD_RESET = "password_reset"


class SecurityToken(Base):
    __tablename__ = "security_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[TokenPurpose] = mapped_column(
        Enum(TokenPurpose, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        index=True,
    )
    #: SHA-256 hex of the raw token. Indexed because looking a token up is the
    #: only read this table ever gets.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    #: Only for EMAIL_CHANGE: the address being proved.
    new_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    #: Set the moment it is spent. A second use is refused by looking here, not
    #: by deleting the row - "this link has already been used" is a far better
    #: message than "this link is not valid", and only a kept row can say it.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    user = relationship("User")

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    def is_expired(self, *, moment: datetime | None = None) -> bool:
        moment = moment or datetime.now(timezone.utc)
        expires = self.expires_at
        # SQLite drops tzinfo on round-trip; normalise before comparing.
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires <= moment

    def is_usable(self, *, moment: datetime | None = None) -> bool:
        return not self.is_used and not self.is_expired(moment=moment)
