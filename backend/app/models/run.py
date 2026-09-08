import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import CaseRunStatus, RunStatus, ToolCallStatus
from app.models.types import utcnow, uuid_pk


class EvaluationRun(Base):
    """One execution of one AgentVersion against one Dataset with one evaluator set.

    Immutable once terminal (ADR-0004): no in-place edits after status leaves
    pending/running. Re-running always creates a new row.
    docs/domain-model.md#evaluationrun
    """

    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    agent_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent_versions.id"), nullable=False
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False
    )
    evaluator_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), nullable=False, default=list
    )
    dataset_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status", native_enum=False),
        nullable=False,
        default=RunStatus.PENDING,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    triggered_by: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    case_runs: Mapped[list["CaseRun"]] = relationship(
        back_populates="evaluation_run", cascade="all, delete-orphan"
    )


class CaseRun(Base):
    """Persisted, normalized result of running one EvaluationCase within one EvaluationRun.

    Holds the adapter's AgentExecutionResult (docs/agent-integration.md). Trace is folded
    in here rather than a separate table (ADR-0006, domain-model.md point 1).
    """

    __tablename__ = "case_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("evaluation_runs.id"), nullable=False
    )
    evaluation_case_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("evaluation_cases.id"), nullable=False
    )
    status: Mapped[CaseRunStatus] = mapped_column(
        Enum(CaseRunStatus, name="case_run_status", native_enum=False), nullable=False
    )
    final_output: Mapped[str | None] = mapped_column(Text)
    structured_output: Mapped[dict | None] = mapped_column(JSONB)
    normalized_trace: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    raw_output: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    latency_ms: Mapped[float] = mapped_column(Numeric, nullable=False)
    token_usage: Mapped[dict | None] = mapped_column(JSONB)
    cost_usd: Mapped[float | None] = mapped_column(Numeric)
    error: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    evaluation_run: Mapped["EvaluationRun"] = relationship(back_populates="case_runs")
    tool_calls: Mapped[list["ToolCall"]] = relationship(
        back_populates="case_run", cascade="all, delete-orphan", order_by="ToolCall.sequence_index"
    )
    results: Mapped[list["EvaluationResult"]] = relationship(
        back_populates="case_run", cascade="all, delete-orphan"
    )


class ToolCall(Base):
    """One tool invocation, extracted from the trace for relational querying.

    docs/domain-model.md#toolcall - kept as its own table only because tool-selection and
    tool-efficiency evaluators need to query/count/order these without parsing JSON.
    """

    __tablename__ = "tool_calls"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("case_runs.id"), nullable=False
    )
    sequence_index: Mapped[int] = mapped_column(nullable=False)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    arguments: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[ToolCallStatus] = mapped_column(
        Enum(ToolCallStatus, name="tool_call_status", native_enum=False), nullable=False
    )
    latency_ms: Mapped[float | None] = mapped_column(Numeric)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    case_run: Mapped["CaseRun"] = relationship(back_populates="tool_calls")


class EvaluationResult(Base):
    """One evaluator's judgment of one CaseRun, on one dimension. docs/domain-model.md"""

    __tablename__ = "evaluation_results"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("case_runs.id"), nullable=False
    )
    evaluator_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("evaluators.id"), nullable=False
    )
    score: Mapped[float] = mapped_column(Numeric, nullable=False)
    passed: Mapped[bool | None] = mapped_column()
    reasoning: Mapped[str | None] = mapped_column(Text)
    raw_output: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    case_run: Mapped["CaseRun"] = relationship(back_populates="results")
