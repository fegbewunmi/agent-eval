import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import EvaluatorType
from app.models.types import utcnow, uuid_pk


class Evaluator(Base):
    """A registered, versioned scorer. docs/domain-model.md#evaluator, ADR-0008.

    (key, version) together identify exactly what logic/config produced a given
    EvaluationResult — a new EvaluationResult-relevant change to config/prompt/logic must
    be a new row (new version), never an in-place edit of an existing one.
    """

    __tablename__ = "evaluators"
    __table_args__ = (UniqueConstraint("key", "version"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[EvaluatorType] = mapped_column(
        Enum(EvaluatorType, name="evaluator_type", native_enum=False), nullable=False
    )
    dimension: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
