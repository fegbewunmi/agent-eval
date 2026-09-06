"""Request/response schemas for the HTTP API layer. Distinct from
app/schemas/execution_result.py, which is the adapter normalization contract — these
shapes are what the API exposes to clients (docs/architecture.md "Backend API").
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class TriggerRunRequest(BaseModel):
    agent_version_id: uuid.UUID
    dataset_id: uuid.UUID
    evaluator_ids: list[uuid.UUID]
    triggered_by: str | None = None
    timeout_seconds: float = 30.0


class DimensionStats(BaseModel):
    dimension: str
    mean_score: float | None  # None when every result for this dimension was n/a
    n: int
    n_not_applicable: int


class CaseRunSummary(BaseModel):
    case_run_id: uuid.UUID
    case_key: str
    status: str
    latency_ms: float


class RunSummaryResponse(BaseModel):
    id: uuid.UUID
    agent_version_id: uuid.UUID
    dataset_id: uuid.UUID
    dataset_snapshot_hash: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    triggered_by: str | None
    dimension_stats: list[DimensionStats]
    case_runs: list[CaseRunSummary]


class ToolCallDetail(BaseModel):
    sequence_index: int
    tool_name: str
    arguments: dict
    result: dict | None
    status: str
    latency_ms: float | None


class EvaluationResultDetail(BaseModel):
    evaluator_key: str
    evaluator_version: str
    dimension: str
    score: float
    passed: bool | None
    reasoning: str | None


class CaseRunDetailResponse(BaseModel):
    case_run_id: uuid.UUID
    case_key: str
    case_input: dict
    case_expected: dict
    status: str
    final_output: str | None
    structured_output: dict | None
    normalized_trace: list[dict]
    latency_ms: float
    token_usage: dict | None
    cost_usd: float | None
    error: dict | None
    tool_calls: list[ToolCallDetail]
    evaluation_results: list[EvaluationResultDetail]


class CaseComparisonEntry(BaseModel):
    case_key: str
    dimension: str
    run_a_score: float | None
    run_a_passed: bool | None
    run_b_score: float | None
    run_b_passed: bool | None


class EvaluatorVersionMismatch(BaseModel):
    dimension: str
    evaluator_key: str
    run_a_version: str
    run_b_version: str


class ComparisonResponse(BaseModel):
    run_a_id: uuid.UUID
    run_b_id: uuid.UUID
    dataset_id: uuid.UUID
    dataset_drift_detected: bool
    evaluator_version_mismatches: list[EvaluatorVersionMismatch]
    dimension_stats: list[DimensionStats]  # for run_b; run_a's own stats are one GET /runs/{id} away
    regressions: list[CaseComparisonEntry]
    improvements: list[CaseComparisonEntry]


# --- Read-only catalog schemas (Phase 4: the frontend needs to browse/select these) ---


class AgentVersionSummary(BaseModel):
    id: uuid.UUID
    version_label: str
    description: str | None
    created_at: datetime


class AgentSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    adapter_key: str
    versions: list[AgentVersionSummary]


class DatasetCaseSummary(BaseModel):
    id: uuid.UUID
    key: str
    tags: list[str]


class DatasetSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    case_count: int


class DatasetDetailResponse(DatasetSummary):
    cases: list[DatasetCaseSummary]


class EvaluatorSummary(BaseModel):
    id: uuid.UUID
    key: str
    version: str
    type: str
    dimension: str
    description: str | None


class RunListItem(BaseModel):
    id: uuid.UUID
    agent_version_id: uuid.UUID
    dataset_id: uuid.UUID
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    triggered_by: str | None
