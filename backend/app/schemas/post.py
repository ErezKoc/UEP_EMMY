import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import UTCDateTime
from app.schemas.user import UserRead


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=10000)
    analysis_id: uuid.UUID | None = None


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content: str
    author: UserRead
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
    created_at: UTCDateTime


class PostDetail(PostRead):
    comments: list[CommentRead]
