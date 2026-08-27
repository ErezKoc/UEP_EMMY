"""What an alert looks like to the client."""

import uuid

from pydantic import BaseModel, ConfigDict

from app.models.email import EmailState
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
    #: Whether the email half went out. True only for `email_state == "sent"`.
    #: Kept for older clients; anything new should read `email_state`.
    emailed: bool
    #: What actually happened to the email, in the four states that are
    #: distinguishable: nothing was meant to go (the reader has email off),
    #: it is waiting in the queue, it went, it was refused, or this deployment
    #: has no mail server at all.
    #:
    #: A boolean could only ever say two of those, which is how the interface
    #: ended up telling somebody their alert was "not emailed" when in fact it
    #: had been queued two seconds earlier and was about to arrive.
    email_state: EmailState
    created_at: UTCDateTime


class UnreadCount(BaseModel):
    unread: int
