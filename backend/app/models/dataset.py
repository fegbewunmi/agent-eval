import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import utcnow, uuid_pk


class Dataset(Base):
    """A named collection of EvaluationCases. docs/domain-model.md#dataset

    Mutable by design (ADR-0003) — case edits are expected over time. Reproducibility of
    historical runs relies on EvaluationRun.dataset_snapshot_hash, not on this being frozen.
    """

    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    cases: Mapped[list["EvaluationCase"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class EvaluationCase(Base):
    """One scenario: an input plus the expected behavior. docs/domain-model.md#evaluationcase

    `input` and `expected` are JSONB with no DB-enforced shape (ADR-0003) — the adapter
    validates `input`, each evaluator validates the parts of `expected` it consumes.
    """

    __tablename__ = "evaluation_cases"
    __table_args__ = (UniqueConstraint("dataset_id", "key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    input: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expected: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    case_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    dataset: Mapped["Dataset"] = relationship(back_populates="cases")
