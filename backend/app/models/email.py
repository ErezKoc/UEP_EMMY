"""The email queue: one row per message we intend to send.

Nothing in the request path talks to an SMTP server. An endpoint that wants an
email writes a row here and returns; a background sweep picks the row up, tries
to deliver it, and writes down what happened. That separation is the whole
point of the table:

* A mail server that is slow, unreachable, or greylisting us cannot make
  "confirm this appointment" take thirty seconds, because the confirmation
  never waits on it.
* A failure is a row to retry rather than an exception to swallow. The previous
  design sent inline and recorded a bare `emailed = False`, which could not
  tell "the server said no" from "there is no server configured" from "we have
  not tried yet" — three states that need three different sentences in front of
  a user.
* `dedupe_key` is unique, so the same message cannot be queued twice however
  many times a caller asks. It carries the same keys the notification layer
  already uses, which is what makes a scheduler that runs every fifteen minutes
  safe to run every fifteen minutes.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmailState(str, enum.Enum):
    """Where one message has got to.

    Four states rather than a boolean, because "did they get the email" has
    four honest answers and a boolean can only give two of them. The column is
    VARCHAR(13), which is exactly the longest value here — see
    `ensure_compatibility_columns`.
    """

    #: The user has email switched off, or this kind of message is not emailed.
    #: Never shown as a failure: nothing was meant to go out.
    NOT_REQUESTED = "not_requested"
    #: Written down, waiting for the sweep. The normal state for a few seconds.
    QUEUED = "queued"
    SENT = "sent"
    #: Tried and refused, out of attempts. Something is wrong at the far end.
    FAILED = "failed"
    #: This deployment has no SMTP server, so the message was written to the
    #: local outbox instead. Distinct from FAILED on purpose - nothing is
    #: broken and there is nothing for the reader to retry.
    UNAVAILABLE = "unavailable"


class EmailCategory(str, enum.Enum):
    """Why we are writing, which decides whether a preference may silence it."""

    #: Reminders, appointments, moderation. Suppressed when `notify_email` is off.
    NOTIFICATION = "notification"
    #: Address verification and password resets. Always deliverable: switching
    #: notifications off is not consent to be locked out of your own account.
    SECURITY = "security"


class EmailMessage(Base):
    __tablename__ = "email_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    #: The address as it was when we queued this. Deliberately a copy rather
    #: than a join to `users.email`: a password-reset message must go to the
    #: address that asked for it, even if the account's address changes while
    #: the message sits in the queue.
    to_email: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(300))
    #: Both bodies, cleared once the message reaches a state it will not leave
    #: (see `email_queue._finish`). A queued password reset necessarily holds
    #: its own link; keeping that link in the database after delivery would
    #: leave a working credential lying about for no benefit.
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    category: Mapped[EmailCategory] = mapped_column(
        Enum(EmailCategory, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        default=EmailCategory.NOTIFICATION,
    )
    #: Unique across the table: queueing the same thing twice is a no-op rather
    #: than a second email.
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True, index=True)

    state: Mapped[EmailState] = mapped_column(
        Enum(EmailState, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        default=EmailState.QUEUED,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    #: When the sweep may next try. Set on every failure, backing off.
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    #: A short, sanitised description of the last outcome. Exception TYPE and
    #: message only - never the body, never credentials. See
    #: `email_queue.describe_failure`.
    detail: Mapped[str | None] = mapped_column(String(300), nullable=True)

    #: The in-app alert this message accompanies, when there is one. NULL for
    #: security mail, which has no notification: telling somebody in the app
    #: to check their email in order to get back into the app is no use.
    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("notifications.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
