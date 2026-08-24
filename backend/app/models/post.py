import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ai_analysis_logs.id", ondelete="SET NULL"), index=True
    )
    image_url: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    author: Mapped["User"] = relationship(back_populates="posts")
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="Comment.created_at",
    )

    @property
    def comment_count(self) -> int:
        return len(self.comments)

    @property
    def has_vet_answer(self) -> bool:
        """Has a VERIFIED veterinarian answered this?

        The single most useful thing a list of questions can say about each
        row, and the reason the community "looks quiet": every post looked
        identical whether it had been answered by a professional or by nobody.
        """
        return any(comment.author.is_verified_vet for comment in self.comments)

    @property
    def last_activity_at(self) -> datetime:
        """When anything last happened here — an answer, or the question itself.

        A question asked in July with an answer this morning is not stale, and
        sorting or labelling by `created_at` alone made the whole board look
        abandoned.
        """
        if not self.comments:
            return self.created_at
        return max(self.created_at, max(comment.created_at for comment in self.comments))


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("posts.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text)

    #: Where the answer comes from, when the person answering chose to say.
    #:
    #: This platform already holds its own clinical advice to a standard of
    #: "name the page it came from" — see services/triage/rules.py, where no
    #: rule may exist without a citation. An answer typed into the community by
    #: a veterinarian reaches an owner exactly the same way, and until now
    #: carried nothing at all.
    #:
    #: Optional, and optional for everyone. Requiring a citation would make the
    #: honest answer "I have seen this a hundred times and it is usually X"
    #: impossible to give, and that answer is worth having.
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    #: What the source is called, so the link is readable. Falls back to the
    #: bare URL when the author does not name it.
    source_title: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    post: Mapped["Post"] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship(back_populates="comments")
    votes: Mapped[list["CommentVote"]] = relationship(
        back_populates="comment", cascade="all, delete-orphan"
    )

    @property
    def helpful_count(self) -> int:
        return len(self.votes)


class CommentVote(Base):
    """One person saying one answer helped them.

    Deliberately one-directional. There is no downvote and there will not be
    one: this is a place where owners bring sick animals and veterinarians
    answer, and a running negative score under a professional's advice would
    discourage exactly the people the platform needs most. "Helpful" is a
    signal that lifts good answers without a mechanism for burying anyone.
    """

    __tablename__ = "comment_votes"
    __table_args__ = (
        # One vote per person per answer, enforced by the database rather than
        # by remembering to check: the endpoint toggles, and a double-submitted
        # request must not be able to count twice.
        UniqueConstraint("comment_id", "user_id", name="uq_comment_vote_once_per_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    comment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("comments.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    comment: Mapped["Comment"] = relationship(back_populates="votes")
