"""What an alert looks like to the client."""

import uuid

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationKind
from app.schemas.common import UTCDateTime


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: NotificationKind
    title: str
    body: str
    link: str | None
    read_at: UTCDateTime | None
    #: Whether the email half went out. Shown in the notification centre so
    #: "I never got the email" has an answer other than a shrug.
    emailed: bool
    created_at: UTCDateTime


class UnreadCount(BaseModel):
    unread: int
