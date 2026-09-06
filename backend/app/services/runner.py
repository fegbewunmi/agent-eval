"""The evaluation execution layer ("the runner"). docs/architecture.md, ADR-0005.

One function, `run_evaluation`, is the single code path for "run a dataset against an
agent version" — called synchronously from a CLI script today (Phase 1) and, later,
from a FastAPI request handler (Phase 2). No task queue, no distributed workers.

Failure isolation (docs/architecture.md "failure boundaries") is the core discipline
here: one case erroring never aborts the run, and one evaluator erroring on one case
never invalidates the other evaluators' results for that same case.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.adapters.registry import get_adapter
from app.evaluators.registry import get_evaluator
from app.models.agent import AgentVersion
from app.models.dataset import Dataset, EvaluationCase
from app.models.enums import CaseRunStatus, RunStatus, ToolCallStatus
from app.models.evaluator import Evaluator
from app.models.run import CaseRun, EvaluationResult, EvaluationRun, ToolCall
from app.schemas.execution_result import AgentExecutionResult, ExecutionError
from app.services.dataset_snapshot import compute_dataset_snapshot_hash


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _execute_with_timeout(adapter, case_input: dict, version_config: dict, timeout_seconds: float) -> AgentExecutionResult:
    """Runner-enforced timeout, independent of whatever the adapter does internally
    (docs/architecture.md "timeout boundary"). Also a defensive catch-all in case an
    adapter fails to normalize its own exceptions, per ADR-0001."""
    started = _utcnow()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(adapter.execute, case_input, version_config)
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError:
            latency_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
            return AgentExecutionResult(
                status="timeout",
                latency_ms=latency_ms,
                raw_output={},
                error=ExecutionError(
                    type="TimeoutError",
                    message=f"Adapter did not return within {timeout_seconds}s",
                ),
            )
        except Exception as exc:  # noqa: BLE001 - defensive: adapter should have caught this itself
            latency_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
            return AgentExecutionResult(
                status="error",
                latency_ms=latency_ms,
                raw_output={},
                error=ExecutionError(
                    type=type(exc).__name__,
                    message=f"Adapter raised without normalizing: {exc}",
                ),
            )


def _persist_case_run(session: Session, run: EvaluationRun, case: EvaluationCase, result: AgentExecutionResult) -> CaseRun:
    case_run = CaseRun(
        evaluation_run_id=run.id,
        evaluation_case_id=case.id,
        status=CaseRunStatus(result.status),
        final_output=result.final_output,
        structured_output=result.structured_output,
        normalized_trace=[step.model_dump(mode="json") for step in result.trace],
        raw_output=result.raw_output,
        latency_ms=result.latency_ms,
        token_usage=result.token_usage.model_dump() if result.token_usage else None,
        cost_usd=result.cost_usd,
        error=result.error.model_dump() if result.error else None,
    )
    session.add(case_run)
    session.flush()

    for tool_call in result.tool_calls:
        session.add(
            ToolCall(
                case_run_id=case_run.id,
                sequence_index=tool_call.sequence_index,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                result=tool_call.result,
                status=ToolCallStatus(tool_call.status),
                latency_ms=tool_call.latency_ms,
                started_at=tool_call.started_at,
            )
        )
    session.flush()
    return case_run


def _run_evaluators(session: Session, case: EvaluationCase, case_run: CaseRun, evaluators: list[Evaluator], execution_result: AgentExecutionResult) -> bool:
    """Returns True if any evaluator failed to produce a result (isolated per evaluator)."""
    any_evaluator_error = False
    for evaluator_row in evaluators:
        try:
            evaluator_impl = get_evaluator(evaluator_row.key, evaluator_row.config)
            eval_results = evaluator_impl.evaluate(case, execution_result)
        except Exception as exc:  # noqa: BLE001 - one evaluator's failure must not affect others
            any_evaluator_error = True
            session.add(
                EvaluationResult(
                    case_run_id=case_run.id,
                    evaluator_id=evaluator_row.id,
                    score=0.0,
                    passed=None,
                    reasoning=f"Evaluator raised an exception: {exc}",
                    raw_output={"evaluator_error": str(exc)},
                )
            )
            continue

        for eval_result in eval_results:
            session.add(
                EvaluationResult(
                    case_run_id=case_run.id,
                    evaluator_id=evaluator_row.id,
                    score=eval_result.score,
                    passed=eval_result.passed,
                    reasoning=eval_result.reasoning,
                    raw_output=eval_result.raw_output,
                )
            )
    session.flush()
    return any_evaluator_error


def run_evaluation(
    session: Session,
    *,
    agent_version_id: uuid.UUID,
    dataset_id: uuid.UUID,
    evaluator_ids: list[uuid.UUID],
    triggered_by: str | None = None,
    timeout_seconds: float = 30.0,
) -> EvaluationRun:
    agent_version = session.get(AgentVersion, agent_version_id)
    if agent_version is None:
        raise ValueError(f"No AgentVersion with id={agent_version_id}")

    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise ValueError(f"No Dataset with id={dataset_id}")

    evaluators = [session.get(Evaluator, eid) for eid in evaluator_ids]
    missing = [eid for eid, ev in zip(evaluator_ids, evaluators) if ev is None]
    if missing:
        raise ValueError(f"Unknown evaluator id(s): {missing}")

    # Queried directly rather than via dataset.cases: that relationship collection can be
    # stale in-memory (e.g. just-loaded dataset file adds cases by FK, not by appending to
    # the relationship) within the same session/process.
    cases = session.query(EvaluationCase).filter_by(dataset_id=dataset.id).order_by(EvaluationCase.key).all()
    run = EvaluationRun(
        agent_version_id=agent_version.id,
        dataset_id=dataset.id,
        evaluator_ids=list(evaluator_ids),
        dataset_snapshot_hash=compute_dataset_snapshot_hash(cases),
        status=RunStatus.RUNNING,
        started_at=_utcnow(),
        triggered_by=triggered_by,
    )
    session.add(run)
    session.flush()

    adapter = get_adapter(agent_version.agent.adapter_key)
    any_failures = False

    for case in cases:
        execution_result = _execute_with_timeout(adapter, case.input, agent_version.config, timeout_seconds)
        if execution_result.status != "success":
            any_failures = True

        case_run = _persist_case_run(session, run, case, execution_result)
        evaluator_failed = _run_evaluators(session, case, case_run, evaluators, execution_result)
        any_failures = any_failures or evaluator_failed

    run.status = RunStatus.COMPLETED_WITH_ERRORS if any_failures else RunStatus.COMPLETED
    run.completed_at = _utcnow()
    session.commit()
    return run
