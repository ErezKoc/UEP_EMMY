import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import VerificationStatus

if TYPE_CHECKING:
    from app.models.user import User


class VetVerification(Base):
    """One credential submission by a veterinarian, plus its review outcome.

    Kept as a history (a rejected vet can resubmit) while `User.verification_status`
    mirrors the newest decision for cheap badge rendering.
    """

    __tablename__ = "vet_verifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Proof of licence (diploma, licence card). Stored via the storage service.
    document_key: Mapped[str] = mapped_column(String(512))
    document_url: Mapped[str] = mapped_column(String(1024))
    # Licence number as claimed at submission time, kept even if the profile changes.
    license_number: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[VerificationStatus] = mapped_column(
        Enum(
            VerificationStatus,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=VerificationStatus.PENDING,
        index=True,
    )
    # Admin's explanation, shown to the veterinarian (especially on rejection).
    review_note: Mapped[str | None] = mapped_column(String(1000))
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    user: Mapped["User"] = relationship(back_populates="verifications", foreign_keys=[user_id])
    reviewed_by: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by_id])

    @property
    def reviewed_by_name(self) -> str | None:
        """Which administrator decided this, so approvals are attributable."""
        return self.reviewed_by.display_name if self.reviewed_by else None
