import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReminderType(str, enum.Enum):
    VACCINE = "vaccine"
    CHECKUP = "checkup"
    OTHER = "other"


class Recurrence(str, enum.Enum):
    """How often, as a unit. How MANY of that unit is `recurrence_interval`.

    `DAILY` and `WEEKLY` were added alongside the interval. The two original
    values keep their exact meaning: a row stored as `monthly` has an interval
    of 1 and still falls on the same day every month, so nothing needed
    rewriting when the column arrived.
    """

    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
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
    #: How many of `recurrence` between occurrences - 3 with MONTHLY is every
    #: three months. Always at least 1; existing rows default to 1, which is
    #: what they already meant.
    recurrence_interval: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    #: The last date this may fall on, or NULL for "keep going".
    #:
    #: A course of treatment ends. Without this, a reminder set for a
    #: three-month course repeats until somebody deletes it, and the
    #: notifications built on top would keep arriving long after the animal
    #: finished the tablets - which is how people learn to ignore them.
    repeat_until: Mapped[date | None] = mapped_column(Date, nullable=True)
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
