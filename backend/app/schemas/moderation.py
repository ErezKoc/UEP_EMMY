import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.moderation import (
    ModerationAction,
    ReportReason,
    ReportStatus,
    ReportTargetType,
)
from app.schemas.common import UTCDateTime
from app.schemas.user import ReportedUserRead, UserSummary


class ReportCreate(BaseModel):
    """What a member submits when reporting a post, comment, or profile.

    The reported account is derived server-side from the target, so a reporter
    cannot aim a report at someone who did not write the content.
    """

    target_type: ReportTargetType
    target_id: uuid.UUID
    # At least one checklist item, so every report states what rule it is about.
    reasons: list[ReportReason] = Field(min_length=1)
    details: str | None = Field(default=None, max_length=2000)


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_type: ReportTargetType
    post_id: uuid.UUID | None
    comment_id: uuid.UUID | None
    content_snapshot: str | None
    reasons: list[ReportReason]
    details: str | None
    status: ReportStatus
    action_taken: ModerationAction | None
    review_note: str | None
    created_at: UTCDateTime
    reviewed_at: UTCDateTime | None
    reviewed_by_name: str | None
    reporter: UserSummary
    # Carries the account's current moderation state so the queue can show
    # whether this member is already suspended or banned.
    reported_user: ReportedUserRead


class ReportDecision(BaseModel):
    """Administrator's outcome for a report.

    `suspend` needs `suspend_days`; `reinstate` clears an earlier penalty. Every
    action except `dismiss` requires a note, enforced in the route.
    """

    action: ModerationAction | None = None
    # True for "reviewed, nothing wrong here". Mutually exclusive with `action`.
    dismiss: bool = False
    suspend_days: int | None = Field(default=None, ge=1, le=365)
    review_note: str | None = Field(default=None, max_length=1000)
