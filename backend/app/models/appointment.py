"""Appointment requests between an owner and a veterinary practice.

Deliberately a REQUEST, not a booking slot. This platform does not hold a
clinic's diary, and pretending otherwise would let an owner leave believing a
time is reserved when the practice has never seen it. So an owner asks for a
day, the practice answers, and only that answer creates anything on a calendar.

The practice's answer may name a different day from the one asked for — that is
the "can you come Thursday instead" conversation, expressed as data rather than
as a second round of messages. The owner sees the day that was confirmed
alongside the day they asked for, so a changed date can never be mistaken for
the one they chose.
"""

import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AppointmentStatus(str, enum.Enum):
    """Where a request has got to.

    There is no "pending owner confirmation" state. A practice that confirms a
    different day has still confirmed something the owner can turn up to, and
    an extra state would leave appointments sitting unanswered in a queue
    nobody watches. If the new day does not suit, the owner cancels.
    """

    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    vet_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: Optional, because an owner can ask about a pet they have not added yet.
    #: A request without one simply produces no calendar entry when confirmed —
    #: reminders belong to a pet, and we do not invent one.
    animal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("animals.id", ondelete="SET NULL"), index=True, nullable=True
    )

    reason: Mapped[str] = mapped_column(String(1000))
    preferred_date: Mapped[date] = mapped_column(Date)
    #: Free text on purpose ("mornings", "after 5pm", "any day that week").
    #: A time picker would imply we know which times the practice has free.
    preferred_time_note: Mapped[str | None] = mapped_column(String(120), nullable=True)

    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(
            AppointmentStatus,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=AppointmentStatus.REQUESTED,
        index=True,
    )

    #: The day the practice confirmed. Kept apart from `preferred_date` rather
    #: than overwriting it, so the owner can always see what they asked for.
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: The practice's reply — a decline reason, or a note about the new day.
    vet_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    #: The calendar entry a confirmation created, so cancelling can remove it
    #: again rather than leaving a reminder for an appointment nobody is having.
    reminder_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("reminders.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    owner = relationship("User", foreign_keys=[owner_id])
    vet = relationship("User", foreign_keys=[vet_id])
    animal = relationship("Animal")

    @property
    def is_open(self) -> bool:
        """Still waiting on the practice."""
        return self.status is AppointmentStatus.REQUESTED
