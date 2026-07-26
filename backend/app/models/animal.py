import enum
import uuid
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.analysis import AIAnalysisLog
    from app.models.user import User


class AgeCategory(str, enum.Enum):
    BABY = "baby"
    YOUNG = "young"
    ADULT = "adult"
    SENIOR = "senior"
    UNKNOWN = "unknown"


class Animal(Base):
    __tablename__ = "animals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    species: Mapped[str] = mapped_column(String(80), index=True)
    breed: Mapped[str | None] = mapped_column(String(120))
    birth_date: Mapped[date | None] = mapped_column(Date)
    photo_url: Mapped[str | None] = mapped_column(String(1024))
    photo_position_x: Mapped[int] = mapped_column(Integer, default=50, server_default="50")
    photo_position_y: Mapped[int] = mapped_column(Integer, default=50, server_default="50")
    photo_zoom: Mapped[float] = mapped_column(Float, default=1.0, server_default="1.0")
    age_category: Mapped[AgeCategory] = mapped_column(
        Enum(AgeCategory, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        default=AgeCategory.UNKNOWN,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    owner: Mapped["User"] = relationship(back_populates="animals")
    analyses: Mapped[list["AIAnalysisLog"]] = relationship(back_populates="animal")
