"""Something the platform wants to tell one person.

One row per thing-worth-saying, per person, regardless of how many ways it goes
out. The channels are delivery, not content: an in-app alert and an email about
the same appointment are the same notification, and storing them separately
would make "mark as read" mean two different things depending on where you
read it.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class NotificationKind(str, enum.Enum):
    """What happened. Drives the icon and, for reminders, the dedupe key."""

    REMINDER_DUE = "reminder_due"
    APPOINTMENT_REQUESTED = "appointment_requested"
    APPOINTMENT_CONFIRMED = "appointment_confirmed"
    APPOINTMENT_DECLINED = "appointment_declined"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    #: Somebody has asked to move a confirmed appointment. Its own kind rather
    #: than reusing REQUESTED, because the two demand different things of the
    #: reader: one is "please answer this", the other is "the thing you already
    #: agreed to may be about to change".
    APPOINTMENT_RESCHEDULE_PROPOSED = "appointment_reschedule_proposed"
    APPOINTMENT_RESCHEDULED = "appointment_rescheduled"
    APPOINTMENT_RESCHEDULE_DECLINED = "appointment_reschedule_declined"
    APPOINTMENT_MESSAGE = "appointment_message"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    kind: Mapped[NotificationKind] = mapped_column(
        Enum(
            NotificationKind,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(1000))
    #: Where clicking it should go, as an in-app path ("/appointments").
    #: Stored rather than derived so an old notification still leads somewhere
    #: sensible after the routes move on.
    link: Mapped[str | None] = mapped_column(String(300), nullable=True)

    #: What this notification is ABOUT, so the same thing is never announced
    #: twice.
    #:
    #: The scheduler runs on a timer and has no memory between runs. Without a
    #: key it would re-announce every reminder due tomorrow on every single
    #: pass, which for a five-minute interval is 288 identical emails a day.
    #: Unique per user: "reminder:<id>:2026-09-01".
    dedupe_key: Mapped[str] = mapped_column(String(200), index=True)

    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Whether the email side of this went out. Kept per notification rather
    #: than assumed, because email can fail while the in-app alert succeeded,
    #: and a retry needs to know which half is missing.
    emailed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    user = relationship("User")

    @property
    def is_read(self) -> bool:
        return self.read_at is not None
