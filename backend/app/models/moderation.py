"""Community reports and the moderation decisions taken on them.

Mirrors the veterinarian-verification flow: a member submits something for
review, an administrator decides, the decision is attributable and reversible,
and the full history is kept while the account carries the current state.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.post import Comment, Post
    from app.models.user import User

# JSONB on PostgreSQL, plain JSON elsewhere (e.g. SQLite in local demos).
_PortableJSON = JSON().with_variant(JSONB(), "postgresql")


class ReportReason(str, enum.Enum):
    """Checklist a reporter ticks. Several may apply to one report."""

    OFFENSIVE_LANGUAGE = "offensive_language"
    HARASSMENT = "harassment"
    SPAM = "spam"
    # Platform-specific: the whole point of the verified badge is that medical
    # advice here is attributable, so impersonation is a first-class category.
    IMPERSONATING_VET = "impersonating_vet"
    HARMFUL_ADVICE = "harmful_advice"
    ANIMAL_WELFARE = "animal_welfare"
    GRAPHIC_CONTENT = "graphic_content"
    OTHER = "other"


class ReportTargetType(str, enum.Enum):
    POST = "post"
    COMMENT = "comment"
    # Reporting the member themselves rather than one piece of content.
    USER = "user"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    # Reviewed, no action against the account.
    DISMISSED = "dismissed"
    # Reviewed, the account was suspended, banned, or later reinstated.
    ACTIONED = "actioned"


class ModerationAction(str, enum.Enum):
    SUSPEND = "suspend"
    BAN = "ban"
    REINSTATE = "reinstate"


class UserReport(Base):
    __tablename__ = "user_reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    reporter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Derived server-side from the reported content — never taken from the client.
    reported_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    target_type: Mapped[ReportTargetType] = mapped_column(
        Enum(ReportTargetType, native_enum=False, values_callable=lambda e: [m.value for m in e])
    )
    # Both NULL for a profile-level report. A reported comment also records its
    # post so the reviewer can open the surrounding discussion.
    post_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("posts.id", ondelete="SET NULL"), index=True
    )
    comment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("comments.id", ondelete="SET NULL"), index=True
    )
    # Copy of the reported text as it read when reported, so the review still
    # makes sense if the author edits or deletes it afterwards.
    content_snapshot: Mapped[str | None] = mapped_column(Text)

    # Ticked checklist values (ReportReason), stored as a list of strings.
    reasons: Mapped[list[Any]] = mapped_column(_PortableJSON, default=list)
    # The reporter's optional free-text explanation.
    details: Mapped[str | None] = mapped_column(String(2000))

    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        default=ReportStatus.PENDING,
        index=True,
    )
    action_taken: Mapped[ModerationAction | None] = mapped_column(
        Enum(ModerationAction, native_enum=False, values_callable=lambda e: [m.value for m in e])
    )
    # The administrator's explanation for the decision.
    review_note: Mapped[str | None] = mapped_column(String(1000))
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    reporter: Mapped["User"] = relationship(foreign_keys=[reporter_id])
    reported_user: Mapped["User"] = relationship(foreign_keys=[reported_user_id])
    reviewed_by: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by_id])
    post: Mapped["Post | None"] = relationship()
    comment: Mapped["Comment | None"] = relationship()

    @property
    def reviewed_by_name(self) -> str | None:
        """Which administrator decided this, so moderation stays attributable."""
        return self.reviewed_by.display_name if self.reviewed_by else None
