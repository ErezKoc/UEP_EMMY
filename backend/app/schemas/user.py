import uuid

from pydantic import BaseModel, ConfigDict

from app.models.user import UserRole
from app.schemas.common import UTCDateTime


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    role: UserRole
    clinic_name: str | None = None
    created_at: UTCDateTime
