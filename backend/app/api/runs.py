"""FastAPI endpoints wrapping the runner and comparison service. docs/roadmap.md Phase 2.

POST /runs still executes synchronously within the request (ADR-0005) — for the dataset
sizes and adapters this platform targets so far, that's a fine tradeoff against standing
up a task queue; revisit only with evidence a real dataset/adapter needs otherwise.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.dataset import EvaluationCase
from app.models.evaluator import Evaluator
from app.models.run import CaseRun, EvaluationResult, EvaluationRun, ToolCall
from app.schemas.api import (
    CaseComparisonEntry,
    CaseRunDetailResponse,
    CaseRunSummary,
    ComparisonResponse,
    DimensionStats,
    EvaluationResultDetail,
    EvaluatorVersionMismatch,
    RunSummaryResponse,
    ToolCallDetail,
    TriggerRunRequest,
)
from app.services.comparison import compare_runs, dimension_stats_for_run
from app.services.runner import run_evaluation

router = APIRouter(prefix="/runs", tags=["runs"])


def _build_run_summary(session: Session, run: EvaluationRun, tag: str | None = None) -> RunSummaryResponse:
    stats = dimension_stats_for_run(session, run.id, tag=tag)
    case_query = (
        session.query(CaseRun, EvaluationCase.key)
        .join(EvaluationCase, CaseRun.evaluation_case_id == EvaluationCase.id)
        .filter(CaseRun.evaluation_run_id == run.id)
    )
    if tag is not None:
        case_query = case_query.filter(EvaluationCase.tags.any(tag))
    case_runs = case_query.order_by(CaseRun.created_at).all()
    return RunSummaryResponse(
        id=run.id,
        agent_version_id=run.agent_version_id,
        dataset_id=run.dataset_id,
        dataset_snapshot_hash=run.dataset_snapshot_hash,
        status=run.status.value,
        started_at=run.started_at,
        completed_at=run.completed_at,
        triggered_by=run.triggered_by,
        dimension_stats=[
            DimensionStats(dimension=s.dimension, mean_score=s.mean_score, n=s.n, n_not_applicable=s.n_not_applicable)
            for s in stats
        ],
        case_runs=[
            CaseRunSummary(case_run_id=cr.id, case_key=key, status=cr.status.value, latency_ms=float(cr.latency_ms))
            for cr, key in case_runs
        ],
    )


@router.post("", response_model=RunSummaryResponse, status_code=201)
def trigger_run(body: TriggerRunRequest, session: Session = Depends(get_db)) -> RunSummaryResponse:
    try:
        run = run_evaluation(
            session,
            agent_version_id=body.agent_version_id,
            dataset_id=body.dataset_id,
            evaluator_ids=body.evaluator_ids,
            triggered_by=body.triggered_by,
            timeout_seconds=body.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _build_run_summary(session, run)


@router.get("/compare", response_model=ComparisonResponse)
def compare(run_a_id: uuid.UUID, run_b_id: uuid.UUID, session: Session = Depends(get_db)) -> ComparisonResponse:
    # Registered before GET /{run_id} below: Starlette matches routes in registration
    # order, and /runs/{run_id} would otherwise swallow /runs/compare, failing UUID
    # parsing on the literal string "compare".
    for run_id in (run_a_id, run_b_id):
        if session.get(EvaluationRun, run_id) is None:
            raise HTTPException(status_code=404, detail=f"No EvaluationRun with id={run_id}")

    try:
        result = compare_runs(session, run_a_id, run_b_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ComparisonResponse(
        run_a_id=result.run_a_id,
        run_b_id=result.run_b_id,
        dataset_id=result.dataset_id,
        dataset_drift_detected=result.dataset_drift_detected,
        evaluator_version_mismatches=[
            EvaluatorVersionMismatch(
                dimension=m.dimension, evaluator_key=m.evaluator_key,
                run_a_version=m.run_a_version, run_b_version=m.run_b_version,
            )
            for m in result.evaluator_version_mismatches
        ],
        dimension_stats=[
            DimensionStats(dimension=s.dimension, mean_score=s.mean_score, n=s.n, n_not_applicable=s.n_not_applicable)
            for s in result.dimension_stats
        ],
        regressions=[
            CaseComparisonEntry(
                case_key=e.case_key, dimension=e.dimension,
                run_a_score=e.run_a_score, run_a_passed=e.run_a_passed,
                run_b_score=e.run_b_score, run_b_passed=e.run_b_passed,
            )
            for e in result.regressions
        ],
        improvements=[
            CaseComparisonEntry(
                case_key=e.case_key, dimension=e.dimension,
                run_a_score=e.run_a_score, run_a_passed=e.run_a_passed,
                run_b_score=e.run_b_score, run_b_passed=e.run_b_passed,
            )
            for e in result.improvements
        ],
    )


@router.get("/{run_id}", response_model=RunSummaryResponse)
def get_run(run_id: uuid.UUID, tag: str | None = None, session: Session = Depends(get_db)) -> RunSummaryResponse:
    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No EvaluationRun with id={run_id}")
    return _build_run_summary(session, run, tag=tag)


@router.get("/{run_id}/cases/{case_run_id}", response_model=CaseRunDetailResponse)
def get_case_run(run_id: uuid.UUID, case_run_id: uuid.UUID, session: Session = Depends(get_db)) -> CaseRunDetailResponse:
    case_run = session.get(CaseRun, case_run_id)
    if case_run is None or case_run.evaluation_run_id != run_id:
        raise HTTPException(status_code=404, detail=f"No CaseRun with id={case_run_id} on run {run_id}")
    case = session.get(EvaluationCase, case_run.evaluation_case_id)

    tool_calls = session.query(ToolCall).filter_by(case_run_id=case_run.id).order_by(ToolCall.sequence_index).all()
    results = session.query(EvaluationResult).filter_by(case_run_id=case_run.id).all()
    evaluators_by_id = {e.id: e for e in session.query(Evaluator).filter(
        Evaluator.id.in_([r.evaluator_id for r in results])
    ).all()}

    return CaseRunDetailResponse(
        case_run_id=case_run.id,
        case_key=case.key,
        case_input=case.input,
        case_expected=case.expected,
        status=case_run.status.value,
        final_output=case_run.final_output,
        structured_output=case_run.structured_output,
        normalized_trace=case_run.normalized_trace,
        latency_ms=float(case_run.latency_ms),
        token_usage=case_run.token_usage,
        cost_usd=float(case_run.cost_usd) if case_run.cost_usd is not None else None,
        error=case_run.error,
        tool_calls=[
            ToolCallDetail(
                sequence_index=tc.sequence_index, tool_name=tc.tool_name, arguments=tc.arguments,
                result=tc.result, status=tc.status.value,
                latency_ms=float(tc.latency_ms) if tc.latency_ms is not None else None,
            )
            for tc in tool_calls
        ],
        evaluation_results=[
            EvaluationResultDetail(
                evaluator_key=evaluators_by_id[r.evaluator_id].key,
                evaluator_version=evaluators_by_id[r.evaluator_id].version,
                dimension=evaluators_by_id[r.evaluator_id].dimension,
                score=float(r.score), passed=r.passed, reasoning=r.reasoning,
            )
            for r in results
        ],
    )
