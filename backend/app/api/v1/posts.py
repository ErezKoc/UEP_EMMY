import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Comment, Post, User
from app.schemas import CommentCreate, CommentRead, PostCreate, PostDetail, PostRead

router = APIRouter()


def _resolve_author(db: Session, author_id: uuid.UUID | None) -> User:
    """Resolve the acting user.

    Placeholder for real authentication: once auth lands, this becomes a
    `get_current_user` dependency and `author_id` disappears from the payloads.
    Until then an explicit id is validated, and omitting it falls back to the
    seeded demo owner so the frontend works out of the box.
    """
    if author_id is not None:
        author = db.get(User, author_id)
        if author is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"User {author_id} not found."
            )
        return author

    author = db.scalars(select(User).order_by(User.created_at).limit(1)).first()
    if author is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No users exist yet; provide an author_id.",
        )
    return author


@router.get("", response_model=list[PostRead])
def list_posts(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Post]:
    """Return recent community posts, newest first."""
    statement = (
        select(Post)
        .options(selectinload(Post.author), selectinload(Post.comments))
        .order_by(Post.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(statement).all())


@router.post("", response_model=PostDetail, status_code=status.HTTP_201_CREATED)
def create_post(payload: PostCreate, db: Session = Depends(get_db)) -> Post:
    author = _resolve_author(db, payload.author_id)
    post = Post(title=payload.title, content=payload.content, author_id=author.id)
    db.add(post)
    db.commit()
    db.refresh(post)
    # Load relationships while the session is open so serialization never
    # triggers a lazy load on a closed session.
    _ = post.author, post.comments
    return post


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Post {post_id} not found."
        )
    return post


@router.post(
    "/{post_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED
)
def create_comment(
    post_id: uuid.UUID, payload: CommentCreate, db: Session = Depends(get_db)
) -> Comment:
    if db.get(Post, post_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Post {post_id} not found."
        )
    author = _resolve_author(db, payload.author_id)
    comment = Comment(post_id=post_id, author_id=author.id, content=payload.content)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment
