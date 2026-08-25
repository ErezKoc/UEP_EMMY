"""Column types shared across models."""

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

#: JSONB on PostgreSQL, plain JSON elsewhere (e.g. SQLite in local demos).
PortableJSON = JSON().with_variant(JSONB(), "postgresql")
