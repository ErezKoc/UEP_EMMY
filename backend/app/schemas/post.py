import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import UTCDateTime
from app.schemas.user import UserRead


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=10000)
    analysis_id: uuid.UUID | None = None


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    #: Where the answer comes from. Optional for everyone — see the model.
    source_url: str | None = Field(default=None, max_length=1024)
    source_title: str | None = Field(default=None, max_length=200)

    @field_validator("source_url")
    @classmethod
    def only_real_links(cls, value: str | None) -> str | None:
        """A citation has to be something a reader can actually open.

        Rejected rather than quietly dropped: an author who typed a source and
        got no error would reasonably believe it had been published with their
        answer.
        """
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("A source must be a link starting with http:// or https://")
        return cleaned


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content: str
    author: UserRead
    source_url: str | None = None
    source_title: str | None = None
    helpful_count: int = 0
    #: Whether the person reading has already marked this helpful, so the
    #: control shows its state instead of inviting a second vote that the
    #: database would reject anyway.
    viewer_found_helpful: bool = False
    created_at: UTCDateTime


class PostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    content: str
    analysis_id: uuid.UUID | None
    image_url: str | None
    author: UserRead
    comment_count: int
    #: Answered by a verified veterinarian. The list's most useful signal, and
    #: the difference between a board that looks alive and one that does not.
    has_vet_answer: bool = False
    last_activity_at: UTCDateTime | None = None
    created_at: UTCDateTime


class PostDetail(PostRead):
    comments: list[CommentRead]
