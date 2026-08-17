import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReminderType(str, enum.Enum):
    VACCINE = "vaccine"
    CHECKUP = "checkup"
    OTHER = "other"


class Recurrence(str, enum.Enum):
    NONE = "none"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    title: Mapped[str] = mapped_column(String(150))
    reminder_type: Mapped[ReminderType] = mapped_column(
        Enum(ReminderType, native_enum=False, values_callable=lambda e: [m.value for m in e])
    )
    due_date: Mapped[date] = mapped_column(Date)
    recurrence: Mapped[Recurrence] = mapped_column(
        Enum(Recurrence, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        default=Recurrence.NONE,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    animal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("animals.id", ondelete="CASCADE"),
        index=True,
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    animal = relationship("Animal")
