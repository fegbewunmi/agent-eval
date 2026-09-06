"""Run-to-run comparison: regression detection between two EvaluationRuns over the same
dataset. docs/evaluation-methodology.md "Regression detection between two runs".

A comparison is a read-only computation over already-immutable data (ADR-0004) — nothing
here is persisted as its own entity, per the "no separate Comparison entity for MVP"
decision in docs/domain-model.md point 5.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.dataset import EvaluationCase
from app.models.evaluator import Evaluator
from app.models.run import CaseRun, EvaluationResult, EvaluationRun


@dataclass
class DimensionStat:
    dimension: str
    mean_score: float | None
    n: int
    n_not_applicable: int


@dataclass
class CaseComparison:
    case_key: str
    dimension: str
    run_a_score: float | None
    run_a_passed: bool | None
    run_b_score: float | None
    run_b_passed: bool | None


@dataclass
class EvaluatorVersionMismatch:
    dimension: str
    evaluator_key: str
    run_a_version: str
    run_b_version: str


@dataclass
class ComparisonResult:
    run_a_id: uuid.UUID
    run_b_id: uuid.UUID
    dataset_id: uuid.UUID
    dataset_drift_detected: bool
    evaluator_version_mismatches: list[EvaluatorVersionMismatch] = field(default_factory=list)
    dimension_stats: list[DimensionStat] = field(default_factory=list)
    regressions: list[CaseComparison] = field(default_factory=list)
    improvements: list[CaseComparison] = field(default_factory=list)


def dimension_stats_for_run(session: Session, run_id: uuid.UUID, tag: str | None = None) -> list[DimensionStat]:
    """Per-dimension mean score for one run, excluding passed=None ("not applicable")
    results from the mean — see docs/evaluation-methodology.md.

    `tag` restricts this to cases carrying that tag (docs/evaluation-methodology.md: "a
    run's summary view should let this matrix be sliced by EvaluationCase.tags") — an
    aggregate over the whole dataset can hide a regression concentrated in one scenario
    category, so this is a real, not cosmetic, capability.
    """
    query = (
        session.query(EvaluationResult, Evaluator.dimension)
        .join(Evaluator, EvaluationResult.evaluator_id == Evaluator.id)
        .join(CaseRun, EvaluationResult.case_run_id == CaseRun.id)
        .filter(CaseRun.evaluation_run_id == run_id)
    )
    if tag is not None:
        query = query.join(EvaluationCase, CaseRun.evaluation_case_id == EvaluationCase.id).filter(
            EvaluationCase.tags.any(tag)
        )
    rows = query.all()
    by_dimension: dict[str, list[float]] = {}
    na_counts: dict[str, int] = {}
    for result, dimension in rows:
        if result.passed is None:
            na_counts[dimension] = na_counts.get(dimension, 0) + 1
        else:
            by_dimension.setdefault(dimension, []).append(float(result.score))

    dimensions = sorted(set(by_dimension) | set(na_counts))
    return [
        DimensionStat(
            dimension=dim,
            mean_score=(sum(by_dimension[dim]) / len(by_dimension[dim])) if by_dimension.get(dim) else None,
            n=len(by_dimension.get(dim, [])),
            n_not_applicable=na_counts.get(dim, 0),
        )
        for dim in dimensions
    ]


def _case_dimension_results(session: Session, run_id: uuid.UUID) -> dict[tuple[str, str], tuple[EvaluationResult, Evaluator]]:
    """Maps (case_key, dimension) -> (EvaluationResult, Evaluator) for one run. Assumes at
    most one evaluator per dimension per case is configured per run — true for every
    evaluator set built so far (docs/phase-notes/); revisit if a run ever configures two
    evaluators reporting the same dimension for the same case.
    """
    rows = (
        session.query(EvaluationResult, Evaluator, EvaluationCase.key)
        .join(Evaluator, EvaluationResult.evaluator_id == Evaluator.id)
        .join(CaseRun, EvaluationResult.case_run_id == CaseRun.id)
        .join(EvaluationCase, CaseRun.evaluation_case_id == EvaluationCase.id)
        .filter(CaseRun.evaluation_run_id == run_id)
        .all()
    )
    return {(case_key, evaluator.dimension): (result, evaluator) for result, evaluator, case_key in rows}


def compare_runs(session: Session, run_a_id: uuid.UUID, run_b_id: uuid.UUID) -> ComparisonResult:
    run_a = session.get(EvaluationRun, run_a_id)
    run_b = session.get(EvaluationRun, run_b_id)
    if run_a is None:
        raise ValueError(f"No EvaluationRun with id={run_a_id}")
    if run_b is None:
        raise ValueError(f"No EvaluationRun with id={run_b_id}")
    if run_a.dataset_id != run_b.dataset_id:
        raise ValueError(
            "Cannot compare runs against different datasets "
            f"(run_a.dataset_id={run_a.dataset_id}, run_b.dataset_id={run_b.dataset_id})"
        )

    results_a = _case_dimension_results(session, run_a_id)
    results_b = _case_dimension_results(session, run_b_id)

    version_mismatches: dict[tuple[str, str], EvaluatorVersionMismatch] = {}
    regressions: list[CaseComparison] = []
    improvements: list[CaseComparison] = []

    for key in sorted(set(results_a) | set(results_b)):
        case_key, dimension = key
        result_a, evaluator_a = results_a.get(key, (None, None))
        result_b, evaluator_b = results_b.get(key, (None, None))

        if evaluator_a and evaluator_b and evaluator_a.key == evaluator_b.key and evaluator_a.version != evaluator_b.version:
            version_mismatches[(dimension, evaluator_a.key)] = EvaluatorVersionMismatch(
                dimension=dimension, evaluator_key=evaluator_a.key,
                run_a_version=evaluator_a.version, run_b_version=evaluator_b.version,
            )

        entry = CaseComparison(
            case_key=case_key, dimension=dimension,
            run_a_score=float(result_a.score) if result_a else None,
            run_a_passed=result_a.passed if result_a else None,
            run_b_score=float(result_b.score) if result_b else None,
            run_b_passed=result_b.passed if result_b else None,
        )

        # Regression/improvement classification is driven by passed transitions, not raw
        # score deltas — a "not applicable" (passed=None) result on either side means
        # there's nothing to classify, consistent with excluding n/a from dimension means.
        if entry.run_a_passed is True and entry.run_b_passed is False:
            regressions.append(entry)
        elif entry.run_a_passed is False and entry.run_b_passed is True:
            improvements.append(entry)

    return ComparisonResult(
        run_a_id=run_a_id,
        run_b_id=run_b_id,
        dataset_id=run_a.dataset_id,
        dataset_drift_detected=run_a.dataset_snapshot_hash != run_b.dataset_snapshot_hash,
        evaluator_version_mismatches=sorted(version_mismatches.values(), key=lambda m: (m.dimension, m.evaluator_key)),
        dimension_stats=dimension_stats_for_run(session, run_b_id),
        regressions=regressions,
        improvements=improvements,
    )
