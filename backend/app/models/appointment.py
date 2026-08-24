"""Appointment requests between an owner and a veterinary practice.

Deliberately a REQUEST, not a booking slot. This platform does not hold a
clinic's diary, and pretending otherwise would let an owner leave believing a
time is reserved when the practice has never seen it. So an owner asks for a
day, the practice answers, and only that answer creates anything on a calendar.

The practice's answer may name a different day from the one asked for - that is
the "can you come Thursday instead" conversation, expressed as data rather than
as a second round of messages. The owner sees the day that was confirmed
alongside the day they asked for, so a changed date can never be mistaken for
the one they chose.

Times are stored NAIVE, and mean the clock on the practice's wall. An
appointment is a physical event at one address: 14:30 at Riverside means 14:30
for the owner walking through its door, whatever timezone their phone thinks it
is in. Converting through UTC would only introduce a way for those two to
disagree, and the failure mode is somebody arriving an hour late.
"""

import enum
import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AppointmentStatus(str, enum.Enum):
    """Where a request has got to.

    There is no "pending owner confirmation" state on the first answer. A
    practice that confirms a different day has still confirmed something the
    owner can turn up to, and an extra state would leave appointments sitting
    unanswered in a queue nobody watches. If the new day does not suit, the
    owner reschedules or cancels.

    `RESCHEDULE_PROPOSED` is different, and does need its own state. A move
    after a confirmation is not a new request: there is an appointment both
    sides have already agreed to, it is on a calendar, and it stays there until
    the other side accepts the move. Folding that back into `REQUESTED` would
    put it in the practice's unanswered queue and lose the agreed booking that
    is still standing underneath.
    """

    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    RESCHEDULE_PROPOSED = "reschedule_proposed"
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
    #: A request without one simply produces no calendar entry when confirmed -
    #: reminders belong to a pet, and we do not invent one.
    animal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("animals.id", ondelete="SET NULL"), index=True, nullable=True
    )

    reason: Mapped[str] = mapped_column(String(1000))
    preferred_date: Mapped[date] = mapped_column(Date)
    #: The clock time the owner would like, or NULL for "no preference".
    #:
    #: Optional on the way in and mandatory on the way out: an owner may
    #: genuinely not mind, and forcing them to invent a time would put a number
    #: in front of the practice that means nothing. What must never be optional
    #: is the time on a CONFIRMED appointment - see `scheduled_time`.
    preferred_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    #: Free text, kept for the rows that were created before `preferred_time`
    #: existed ("mornings", "after 5pm"). No longer offered by the composer -
    #: a real time field replaced it - but still displayed where it is set,
    #: because deleting somebody's stated preference is not a migration.
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
    #: The clock time the practice confirmed.
    #:
    #: Required by the API on every confirmation, and nullable here only
    #: because rows confirmed before this column existed have no time to give.
    #: "Confirmed for 12 Sep" is not an appointment - the owner still has to
    #: ring up and ask the one question the confirmation was supposed to
    #: answer, which is what this whole field is here to stop.
    scheduled_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    #: The practice's reply - a decline reason, or a note about the new day.
    vet_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # ------------------------------------------------- a move under discussion
    #
    # These four hold a proposal that has not been agreed yet. They are kept
    # apart from `scheduled_date`/`scheduled_time` on purpose: the appointment
    # both sides already agreed to is still standing, still on the calendar,
    # and still the one to turn up to until somebody accepts the move. Writing
    # a proposal straight into the scheduled fields would silently move a
    # calendar entry on the strength of one party's suggestion.
    proposed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    proposed_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    #: Who suggested it, because only the OTHER side may answer it. Without
    #: this the proposer could accept their own proposal.
    proposed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    proposed_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)

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
    proposed_by = relationship("User", foreign_keys=[proposed_by_id])
    messages: Mapped[list["AppointmentMessage"]] = relationship(
        back_populates="appointment",
        cascade="all, delete-orphan",
        order_by="AppointmentMessage.created_at",
    )

    @property
    def is_open(self) -> bool:
        """Still waiting on the practice's first answer."""
        return self.status is AppointmentStatus.REQUESTED

    @property
    def has_pending_reschedule(self) -> bool:
        return self.status is AppointmentStatus.RESCHEDULE_PROPOSED


class AppointmentMessage(Base):
    """One line of the conversation about one appointment.

    Attached to the appointment rather than being a general inbox, and that is
    the whole design. A clinic does not want a chat client; it wants "is he
    still limping?" to be readable next to the appointment it is about, six
    weeks later, by whoever picks the case up. Threading it anywhere else means
    the context is a search away at the moment it is needed.

    There is no edit and no delete. This is a clinical conversation that leads
    to somebody being seen or not being seen, and a message that can change
    after it has been read is a record neither side can rely on.
    """

    __tablename__ = "appointment_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("appointments.id", ondelete="CASCADE"), index=True
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text)
    #: When the OTHER party opened the thread and saw this. Drives the unread
    #: badge, and also decides whether a further message is worth a second
    #: notification - see the messages endpoint.
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    appointment: Mapped["Appointment"] = relationship(back_populates="messages")
    sender = relationship("User")
