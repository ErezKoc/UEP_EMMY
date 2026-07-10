from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator


def _ensure_utc(value: datetime) -> datetime:
    """Attach UTC to naive datetimes so API timestamps always carry an offset.

    The models store UTC, but some backends (notably SQLite) drop tzinfo on
    round-trip; without this, browsers would parse the ISO string as local time.
    """
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


UTCDateTime = Annotated[datetime, AfterValidator(_ensure_utc)]
