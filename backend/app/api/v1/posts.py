import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import AIAnalysisLog, Comment, Post, User, UserRole
from app.schemas import CommentCreate, CommentRead, PostCreate, PostDetail, PostRead

router = APIRouter()


@router.get("", response_model=list[PostRead])
def list_posts(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=100),
    author_role: UserRole | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Post]:
    """Return recent community posts with optional topic and author filters."""
    statement = (
        select(Post)
        .join(Post.author)
        .options(selectinload(Post.author), selectinload(Post.comments))
        .order_by(Post.created_at.desc())
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
    return list(db.scalars(statement).unique().all())


@router.post("", response_model=PostDetail, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
def get_post(post_id: uuid.UUID, db: Session = Depends(get_db)) -> Post:
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
    return post


@router.post(
    "/{post_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED
)
def create_comment(
    post_id: uuid.UUID,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Comment:
    if db.get(Post, post_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post {post_id} not found.")
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Comment is required.")
    comment = Comment(post_id=post_id, author_id=current_user.id, content=content)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    _ = comment.author
    return comment
