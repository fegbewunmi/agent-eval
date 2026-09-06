import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import mapped_column


def uuid_pk():
    """Standard UUID primary key column, per docs/domain-model.md (every entity uses UUID ids)."""
    return mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
