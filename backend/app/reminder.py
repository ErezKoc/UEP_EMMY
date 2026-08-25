import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
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

    #: How many days ahead THIS reminder is announced, or NULL for the account
    #: default.
    #:
    #: One lead time for everything was the wrong shape. A rabies booster is
    #: worth a week's warning because it needs an appointment; the tablet due
    #: tonight is worth none, because there is nothing to arrange. Forcing both
    #: through one number means either the booster arrives too late to book or
    #: the tablet nags for a week, and the second is how people learn to ignore
    #: the first.
    #:
    #: NULL rather than a copy of the account value, so changing the account
    #: default still moves everything that never asked for something different.
    notify_lead_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

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

    #: Only the occurrences somebody has acted on. Sparse on purpose - see the
    #: class below.
    occurrences: Mapped[list["ReminderOccurrence"]] = relationship(
        back_populates="reminder", cascade="all, delete-orphan"
    )


class ReminderOccurrence(Base):
    """One dated instance of a reminder that somebody has done or postponed.

    Sparse: a row exists only where an occurrence has been acted on. A weekly
    reminder running for two years is 104 dates, and materialising all of them
    so that three can be ticked would turn a five-row table into a five-hundred
    row one whose contents are almost entirely derivable. The schedule stays
    computed; this table records only the deviations from it.

    `occurrence_date` is the date the schedule ORIGINALLY produced, and it is
    the identity. Snoozing writes `snoozed_to` and leaves it alone, so a
    reminder pushed from the 3rd to the 5th is still recognisably the 3rd's
    dose - which matters, because the 3rd is the date the recurrence arithmetic
    will keep generating and the date every notification was keyed on.

    Completion is per occurrence rather than per reminder for the same reason.
    "Done" on a monthly worming treatment means this month's is done, not that
    the treatment is over; storing it on the reminder itself would force a
    choice between losing the series and losing the record.
    """

    __tablename__ = "reminder_occurrences"
    __table_args__ = (
        # One row per dated instance, enforced by the database rather than by
        # remembering to check: two "done" rows for the same date would make
        # the completed count wrong in a way nobody would ever look for.
        UniqueConstraint("reminder_id", "occurrence_date", name="uq_reminder_occurrence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    reminder_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reminders.id", ondelete="CASCADE"), index=True
    )
    #: The scheduled date. Never rewritten - snoozing sets `snoozed_to`.
    occurrence_date: Mapped[date] = mapped_column(Date, index=True)

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: Where this one instance has been moved to. The series is untouched: next
    #: month's dose is still due next month, whatever happened to this one.
    snoozed_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    reminder: Mapped["Reminder"] = relationship(back_populates="occurrences")

    @property
    def is_done(self) -> bool:
        return self.completed_at is not None

    @property
    def effective_date(self) -> date:
        """When this instance is actually due, after any snooze."""
        return self.snoozed_to or self.occurrence_date
