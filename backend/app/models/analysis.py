import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.animal import Animal

# JSONB on PostgreSQL, plain JSON elsewhere (e.g. SQLite in local demos).
PortableJSON = JSON().with_variant(JSONB(), "postgresql")


class AIAnalysisLog(Base):
    __tablename__ = "ai_analysis_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Who ran the analysis. Nullable: anonymous uploads (e.g. the public
    # dashboard demo) are stored but belong to nobody's history.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    # Nullable: an owner can analyze a photo before registering the animal.
    animal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("animals.id", ondelete="SET NULL"), index=True
    )
    image_key: Mapped[str] = mapped_column(String(512))
    image_url: Mapped[str] = mapped_column(String(1024))
    model_version: Mapped[str] = mapped_column(String(64))
    species: Mapped[str] = mapped_column(String(80))
    species_confidence: Mapped[float] = mapped_column(Float)
    # Full structured payload returned by the analysis service, kept verbatim
    # so results remain reproducible after the mock is swapped for Rekognition.
    result: Mapped[dict[str, Any]] = mapped_column(PortableJSON)
    # Symptom triage, when the owner answered the intake questions. Stored
    # verbatim so a past verdict stays reproducible after the rules change,
    # and indexed by level so the vet queue can sort by urgency later.
    intake: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    triage: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    triage_level: Mapped[str | None] = mapped_column(String(10), index=True)
    #: What the owner says the animal actually is, when the model got it wrong.
    #:
    #: A separate column rather than an edit to `result`, and that is the whole
    #: design. `result` is the model's own output, kept verbatim so a past
    #: answer stays reproducible - overwriting it to fix a breed would destroy
    #: the record of what was actually predicted, which is the only thing that
    #: makes the analysis auditable at all. The correction layers on top: the
    #: interface shows the owner's version, and both remain readable.
    #:
    #: Shape: {"species": str|None, "breed": str|None, "age_category": str|None,
    #: "note": str|None}. Any key may be absent or null, meaning "the model's
    #: value stands for this field".
    correction: Mapped[dict[str, Any] | None] = mapped_column(PortableJSON)
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    animal: Mapped["Animal | None"] = relationship(back_populates="analyses")
