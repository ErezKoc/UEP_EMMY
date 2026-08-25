"""Openings a practice has published on this platform.

This is the only honest form "real availability" can take here. The platform
has no connection to whatever software runs a clinic's diary, and the
appointment flow is built on saying so - an owner who leaves believing a time
is reserved when the practice has never seen it ends up at a closed door with a
sick animal.

So a slot is not a window into the clinic's calendar. It is the practice
declaring, on this platform, "we have this time free". That claim is real
because they made it, and it is the only kind we can stand behind. The
interface says "published by the practice" everywhere for that reason, and a
practice with no slots is reported as "no times published", never as "fully
booked" - a clinic that has not filled this in is not a clinic with no room.

A slot still produces a REQUEST, not a booking. Picking one tells the practice
exactly which time is wanted instead of leaving them to guess from "mornings",
and the practice still answers. Consuming the slot on confirmation is what
stops two owners being sent the same time.
"""

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Time, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AvailabilitySlot(Base):
    """One published opening at one practice."""

    __tablename__ = "availability_slots"
    __table_args__ = (
        # A practice cannot publish the same start time twice on one day.
        # Without this, a double-tap on "publish" produces two slots that look
        # identical to an owner and hold two different ids.
        UniqueConstraint("vet_id", "slot_date", "start_time", name="uq_slot_once_per_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    vet_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    slot_date: Mapped[date] = mapped_column(Date, index=True)
    #: Naive, and meaning the clock on the practice's wall - the same rule as
    #: appointment times. A slot is a physical event at one address.
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)

    #: How many animals can be seen in this slot.
    #:
    #: Usually 1. More than 1 exists because some practices run open surgeries
    #: where several owners are told the same hour and seen in order, and
    #: forcing those onto separate slots would misrepresent how the practice
    #: actually works.
    capacity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    #: What this slot is for, when it is not a general consultation
    #: ("vaccinations only", "nurse appointment").
    note: Mapped[str | None] = mapped_column(String(200))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    vet = relationship("User")
    #: Requests pointing at this slot. Only CONFIRMED ones consume capacity -
    #: see `taken`.
    appointments = relationship("Appointment", back_populates="slot")

    @property
    def taken(self) -> int:
        """How much of this slot is already spoken for.

        Counts confirmed appointments only. An unanswered request must not
        hide the slot from everybody else: the practice may yet decline it, and
        a slot held by a request nobody has answered is a slot quietly lost.
        """
        # Imported here rather than at module scope: appointment.py imports
        # this module for its own relationship, and at import time neither is
        # finished being defined.
        from app.models.appointment import AppointmentStatus

        return sum(
            1
            for appointment in self.appointments
            if appointment.status
            in (AppointmentStatus.CONFIRMED, AppointmentStatus.RESCHEDULE_PROPOSED)
        )

    @property
    def is_open(self) -> bool:
        return self.taken < self.capacity
