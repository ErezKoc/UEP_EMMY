import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.analysis import PortableJSON
from app.models.animal import AgeCategory

if TYPE_CHECKING:
    from app.models.animal import Animal

    from app.models.user import User


class SymptomCheck(Base):
    """A saved symptom assessment, made without a photo.

    Kept separate from `AIAnalysisLog` rather than folded into it: that table
    requires an image and a model result on every row, and this record has
    neither. SQLite cannot drop a NOT NULL constraint in place, so widening the
    analysis table would need a full rebuild — a new table is both cleaner and
    safer for the existing demo databases.
    """

    __tablename__ = "symptom_checks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Not nullable, unlike analyses: an anonymous check is simply not saved, so
    # every stored row belongs to somebody's history.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Nullable: an owner can check symptoms for a pet they have not added yet.
    animal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("animals.id", ondelete="SET NULL"), index=True
    )
    # What the owner said, and what the engine answered. Both stored verbatim so
    # a past verdict stays readable after the rule table changes.
    intake: Mapped[dict[str, Any]] = mapped_column(PortableJSON)
    triage: Mapped[dict[str, Any]] = mapped_column(PortableJSON)
    # Widened from 10 to 32 when `unassessed` was added: that value is exactly
    # 10 characters, so the old column fitted it with nothing to spare and the
    # next level name would have overflowed on Postgres. SQLite ignores VARCHAR
    # length, so existing demo databases need no migration; a Postgres
    # deployment needs one widening ALTER — see
    # migrations/0001_triage_level_varchar32.sql.
    triage_level: Mapped[str] = mapped_column(String(32), index=True)
    # Copied out of the intake so the history list can label a row without
    # having to parse the stored JSON.
    species: Mapped[str | None] = mapped_column(String(80))
    age_category: Mapped[AgeCategory | None] = mapped_column(
        Enum(AgeCategory, native_enum=False, values_callable=lambda e: [m.value for m in e])
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    animal: Mapped["Animal | None"] = relationship(back_populates="symptom_checks")
