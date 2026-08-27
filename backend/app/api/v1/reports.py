"""Community reporting and account moderation.

A member reports a post, a comment, or a profile with a reason checklist and an
optional explanation. Administrators review the queue and either dismiss the
report or suspend/ban the account — every decision attributable, reversible,
and explained to the member it affects.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_active_user, get_current_admin, get_current_user
from app.db.session import get_db
from app.models import (
    AccountStatus,
    Comment,
    ModerationAction,
    Post,
    ReportStatus,
    ReportTargetType,
    User,
    UserReport,
    UserRole,
)
from app.models.notification import NotificationKind
from app.schemas import ReportCreate, ReportDecision, ReportRead
from app.services.notifications import notify

router = APIRouter()

# Loaded on every read so serialising a report never lazy-loads on a closed session.
_RELATIONS = (
    selectinload(UserReport.reporter),
    selectinload(UserReport.reported_user),
    selectinload(UserReport.reviewed_by),
)


def _resolve_target(
    db: Session, payload: ReportCreate
) -> tuple[User, uuid.UUID | None, uuid.UUID | None, str | None]:
    """Find who is being reported, plus the context an administrator will need.

    Returns (reported_user, post_id, comment_id, content_snapshot). The snapshot
    is a copy of the text as reported, so the review still makes sense if the
    author edits or deletes it afterwards.
    """
    if payload.target_type == ReportTargetType.POST:
        post = db.get(Post, payload.target_id)
        if post is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Post {payload.target_id} not found.",
            )
        return post.author, post.id, None, f"{post.title}\n\n{post.content}"

    if payload.target_type == ReportTargetType.COMMENT:
        comment = db.get(Comment, payload.target_id)
        if comment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Comment {payload.target_id} not found.",
            )
        # Record the parent post too, so the reviewer can open the discussion.
        return comment.author, comment.post_id, comment.id, comment.content

    reported = db.get(User, payload.target_id)
    if reported is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User {payload.target_id} not found."
        )
    return reported, None, None, None


@router.post("", response_model=ReportRead, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_active_user),
) -> UserReport:
    """Report a post, comment, or profile for administrator review."""
    reported_user, post_id, comment_id, snapshot = _resolve_target(db, payload)

    if reported_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You cannot report your own content.",
        )
    if reported_user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Administrator accounts cannot be reported here.",
        )

    # One open report per reporter per target: re-reporting the same thing adds
    # nothing to the queue and lets one member flood it.
    conditions = [
        UserReport.reporter_id == current_user.id,
        UserReport.reported_user_id == reported_user.id,
        UserReport.target_type == payload.target_type,
        UserReport.status == ReportStatus.PENDING,
    ]
    if payload.target_type == ReportTargetType.POST:
        conditions.append(UserReport.post_id == post_id)
    elif payload.target_type == ReportTargetType.COMMENT:
        conditions.append(UserReport.comment_id == comment_id)
    duplicate = db.scalars(select(UserReport).where(*conditions).limit(1)).first()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already reported this, and it is still awaiting review.",
        )

    report = UserReport(
        reporter_id=current_user.id,
        reported_user_id=reported_user.id,
        target_type=payload.target_type,
        post_id=post_id,
        comment_id=comment_id,
        content_snapshot=snapshot,
        reasons=[reason.value for reason in payload.reasons],
        details=(payload.details or "").strip() or None,
        status=ReportStatus.PENDING,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    _ = report.reporter, report.reported_user
    return report


@router.get("/me", response_model=list[ReportRead])
def my_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UserReport]:
    """Reports the caller has filed, newest first."""
    statement = (
        select(UserReport)
        .options(*_RELATIONS)
        .where(UserReport.reporter_id == current_user.id)
        .order_by(UserReport.created_at.desc())
    )
    return list(db.scalars(statement).all())


@router.get("", response_model=list[ReportRead])
def list_reports(
    status_filter: ReportStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> list[UserReport]:
    """Review queue: oldest first, so the longest-waiting report is handled first."""
    statement = select(UserReport).options(*_RELATIONS).order_by(UserReport.created_at)
    if status_filter is not None:
        statement = statement.where(UserReport.status == status_filter)
    return list(db.scalars(statement).all())


@router.patch("/{report_id}", response_model=ReportRead)
def decide_report(
    report_id: uuid.UUID,
    payload: ReportDecision,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> UserReport:
    """Dismiss a report, or suspend/ban/reinstate the reported account.

    Suspending or banning silences a member, so — like approving a verification
    — it always carries a written reason. Decisions are not final: deciding the
    same report again with `reinstate` restores the account.
    """
    report = db.get(UserReport, report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Report {report_id} not found."
        )

    if payload.dismiss == (payload.action is not None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide exactly one of 'dismiss' or 'action'.",
        )

    note = (payload.review_note or "").strip() or None
    if payload.action is not None and note is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Suspending, banning, or reinstating an account requires a reason.",
        )

    reported = report.reported_user
    if payload.dismiss:
        report.status = ReportStatus.DISMISSED
        report.action_taken = None
    elif payload.action == ModerationAction.SUSPEND:
        if payload.suspend_days is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A suspension needs a duration in days.",
            )
        reported.account_status = AccountStatus.SUSPENDED
        reported.suspended_until = datetime.now(timezone.utc) + timedelta(days=payload.suspend_days)
        reported.moderation_note = note
        report.status = ReportStatus.ACTIONED
        report.action_taken = ModerationAction.SUSPEND
    elif payload.action == ModerationAction.BAN:
        reported.account_status = AccountStatus.BANNED
        reported.suspended_until = None
        reported.moderation_note = note
        report.status = ReportStatus.ACTIONED
        report.action_taken = ModerationAction.BAN
    else:  # ModerationAction.REINSTATE
        reported.account_status = AccountStatus.ACTIVE
        reported.suspended_until = None
        reported.moderation_note = None
        report.status = ReportStatus.ACTIONED
        report.action_taken = ModerationAction.REINSTATE

    report.review_note = note
    report.reviewed_by_id = admin.id
    report.reviewed_at = datetime.now(timezone.utc)

    # A dismissal is not told to anybody. The reported member never knew a
    # report existed, and announcing "somebody reported you, and we decided it
    # was nothing" would create a grievance out of a non-event.
    if report.action_taken is not None:
        _announce_moderation(db, report, reported, report.action_taken, note)

    db.commit()
    db.refresh(report)
    _ = report.reporter, report.reported_user, report.reviewed_by
    return report


def _announce_moderation(
    db: Session,
    report: UserReport,
    member: User,
    action: ModerationAction,
    note: str | None,
) -> None:
    """Tell a member about a decision that changes what their account can do.

    Only ever for a decision they can feel. A suspension, a ban and a
    reinstatement all change what happens when they next open the app, and
    finding that out by being refused is worse than being told.

    The moderator's reason is carried through. Every one of these is required
    to have one - the endpoint refuses the decision otherwise - precisely so
    this message is never "your account has been suspended" and nothing else.
    """
    if action is ModerationAction.SUSPEND:
        title = "Your account has been suspended"
        until = (
            f" until {member.suspended_until:%d %b %Y}"
            if member.suspended_until is not None
            else ""
        )
        body = (
            f"An administrator has suspended your UEP EMMY account{until}. You can "
            "still sign in and read the platform; posting, commenting and reporting "
            "are paused."
        )
    elif action is ModerationAction.BAN:
        title = "Your account has been banned"
        body = (
            "An administrator has banned your UEP EMMY account for breaking the "
            "community rules. You can no longer sign in."
        )
    else:
        title = "Your account has been reinstated"
        body = (
            "An administrator has lifted the restriction on your UEP EMMY account. "
            "You can post, comment and report again."
        )
    if note:
        body += f" They said: {note}"

    facts: list[tuple[str, str]] = [("Decision", action.value)]
    if action is ModerationAction.SUSPEND and member.suspended_until is not None:
        facts.append(("Until", f"{member.suspended_until:%d %b %Y}"))

    notify(
        db,
        user=member,
        kind=NotificationKind.MODERATION_DECISION,
        title=title,
        body=body,
        # Keyed on the report and the verdict, not on the account. Two separate
        # reports leading to two suspensions are two things the member is owed
        # an explanation for; the same report re-decided the same way is one,
        # and re-announcing it would read as a second punishment.
        dedupe_key=f"moderation:{report.id}:{action.value}",
        link="/profile",
        email_facts=facts,
    )
