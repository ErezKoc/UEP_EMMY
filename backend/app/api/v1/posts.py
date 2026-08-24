import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_active_user, get_optional_user
from app.db.session import get_db
from app.models import (
    AIAnalysisLog,
    Comment,
    CommentVote,
    Post,
    User,
    UserRole,
    VerificationStatus,
)
from app.schemas import CommentCreate, CommentRead, PostCreate, PostDetail, PostRead

router = APIRouter()


def _with_viewer(comment: Comment, viewer: User | None) -> CommentRead:
    """One answer, told from the reader's point of view.

    `viewer_found_helpful` cannot come off the row on its own — it depends on
    who is asking — so it is filled in here rather than left for each client to
    work out from a list of voter ids we would then have to send.
    """
    data = CommentRead.model_validate(comment)
    data.helpful_count = len(comment.votes)
    data.viewer_found_helpful = viewer is not None and any(
        vote.user_id == viewer.id for vote in comment.votes
    )
    return data


@router.post("/comments/{comment_id}/helpful", response_model=CommentRead)
def toggle_helpful(
    comment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_active_user),
) -> CommentRead:
    """Mark an answer helpful, or take it back.

    A toggle rather than two endpoints: the button has one visible state and
    pressing it again is the obvious way to undo, and a client that loses track
    of whether it has voted cannot end up double-counting.

    Voting on your own answer is refused. It costs nothing to allow and buys a
    number nobody can trust.
    """
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found.")
    if comment.author_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot mark your own answer helpful.",
        )

    existing = db.scalars(
        select(CommentVote).where(
            CommentVote.comment_id == comment_id, CommentVote.user_id == current_user.id
        )
    ).first()
    if existing is not None:
        db.delete(existing)
    else:
        db.add(CommentVote(comment_id=comment_id, user_id=current_user.id))
    db.commit()
    db.refresh(comment)
    return _with_viewer(comment, current_user)


@router.get("", response_model=list[PostRead])
def list_posts(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=100),
    author_role: UserRole | None = Query(default=None),
    answered: bool | None = Query(default=None),
    vet_answered: bool | None = Query(default=None),
    sort: str = Query(default="recent", pattern="^(recent|active|discussed)$"),
    db: Session = Depends(get_db),
) -> list[Post]:
    """Recent community posts, filtered and sorted.

    `answered=false` is the one that matters most and the one that was missing:
    somebody willing to help had no way to find the questions nobody had
    answered, so they scrolled a list sorted by date and gave up. A board where
    the unanswered questions are unfindable is a board that stays quiet.
    """
    statement = (
        select(Post)
        .join(Post.author)
        .options(selectinload(Post.author), selectinload(Post.comments).selectinload(Comment.author))
        .limit(limit)
        .offset(offset)
    )
    if q and (term := q.strip()):
        pattern = f"%{term}%"
        statement = statement.where(
            or_(Post.title.ilike(pattern), Post.content.ilike(pattern), User.display_name.ilike(pattern))
        )
    if author_role is not None:
        statement = statement.where(User.role == author_role)

    if answered is not None:
        has_any = select(Comment.id).where(Comment.post_id == Post.id).exists()
        statement = statement.where(has_any if answered else ~has_any)

    if vet_answered is not None:
        # A VERIFIED veterinarian, not merely an account claiming to be one —
        # the badge and this filter have to mean the same thing or neither is
        # worth anything.
        vet_reply = (
            select(Comment.id)
            .join(User, Comment.author_id == User.id)
            .where(
                Comment.post_id == Post.id,
                User.role == UserRole.VETERINARIAN,
                User.verification_status == VerificationStatus.VERIFIED,
            )
            .exists()
        )
        statement = statement.where(vet_reply if vet_answered else ~vet_reply)

    if sort == "discussed":
        comment_count = (
            select(func.count(Comment.id)).where(Comment.post_id == Post.id).scalar_subquery()
        )
        statement = statement.order_by(comment_count.desc(), Post.created_at.desc())
    elif sort == "active":
        # Last reply, falling back to when the question was asked. A question
        # from July answered this morning belongs at the top, and sorting by
        # `created_at` alone is what made the board look abandoned.
        latest_reply = (
            select(func.max(Comment.created_at))
            .where(Comment.post_id == Post.id)
            .scalar_subquery()
        )
        statement = statement.order_by(func.coalesce(latest_reply, Post.created_at).desc())
    else:
        statement = statement.order_by(Post.created_at.desc())

    return list(db.scalars(statement).unique().all())


@router.post("", response_model=PostDetail, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_active_user),
) -> Post:
    title = payload.title.strip()
    content = payload.content.strip()
    if not title or not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Title and content are required.")

    image_url: str | None = None
    if payload.analysis_id is not None:
        analysis = db.get(AIAnalysisLog, payload.analysis_id)
        if analysis is None or analysis.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis {payload.analysis_id} not found.",
            )
        image_url = analysis.image_url

    post = Post(
        title=title,
        content=content,
        author_id=current_user.id,
        analysis_id=payload.analysis_id,
        image_url=image_url,
    )
    db.add(post)
    db.commit()
    return get_post(post.id, db)


@router.get("/{post_id}", response_model=PostDetail)
def get_post(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
) -> PostDetail:
    statement = (
        select(Post)
        .options(
            selectinload(Post.author),
            selectinload(Post.comments).selectinload(Comment.author),
        )
        .where(Post.id == post_id)
    )
    post = db.scalars(statement).first()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post {post_id} not found.")

    # Built by hand rather than returned raw, because each answer's
    # "you found this helpful" depends on who is reading.
    detail = PostDetail.model_validate(post)
    detail.comments = [_with_viewer(comment, viewer) for comment in post.comments]
    return detail


@router.post(
    "/{post_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED
)
def create_comment(
    post_id: uuid.UUID,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_active_user),
) -> Comment:
    if db.get(Post, post_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post {post_id} not found.")
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Comment is required.")
    comment = Comment(
        post_id=post_id,
        author_id=current_user.id,
        content=content,
        source_url=payload.source_url,
        # A title with no link is a label for nothing, so it only survives
        # alongside one.
        source_title=(payload.source_title or "").strip() or None if payload.source_url else None,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    _ = comment.author
    return comment
