"""End-to-end runner tests against a real Postgres schema (docs/roadmap.md Phase 1 exit
criteria): run the smoke dataset through the stub adapter and confirm both normal scoring
and failure isolation (a crashing case doesn't abort the run; a crashing evaluator doesn't
invalidate other evaluators' results for the same case)."""

from pathlib import Path

import pytest

from app.evaluators import registry as evaluator_registry
from app.evaluators.base import Evaluator
from app.models.dataset import EvaluationCase
from app.models.enums import CaseRunStatus, EvaluatorType, RunStatus
from app.models.run import CaseRun, EvaluationResult
from app.services.dataset_loader import load_dataset_from_file
from app.services.runner import run_evaluation
from app.services.seed import ensure_agent, ensure_agent_version, ensure_evaluator

DATASET_FILE = Path(__file__).resolve().parents[3] / "datasets" / "stub-agent" / "smoke-v1" / "cases.yaml"


def _seed_run_inputs(session):
    dataset = load_dataset_from_file(session, DATASET_FILE)
    agent = ensure_agent(session, name="stub-agent", adapter_key="stub-agent")
    agent_version = ensure_agent_version(session, agent=agent, version_label="v1", config={})
    evaluators = [
        ensure_evaluator(session, key="structured_field_exact_match", version="v1",
                          type=EvaluatorType.DETERMINISTIC, dimension="task_correctness"),
        ensure_evaluator(session, key="completion_check", version="v1",
                          type=EvaluatorType.DETERMINISTIC, dimension="completion"),
    ]
    session.flush()
    return dataset, agent_version, evaluators


def test_full_run_isolates_case_level_failures(session):
    dataset, agent_version, evaluators = _seed_run_inputs(session)

    run = run_evaluation(
        session,
        agent_version_id=agent_version.id,
        dataset_id=dataset.id,
        evaluator_ids=[e.id for e in evaluators],
    )

    assert run.status == RunStatus.COMPLETED_WITH_ERRORS  # crash + wrong-answer cases present
    case_runs = session.query(CaseRun).filter_by(evaluation_run_id=run.id).all()
    assert len(case_runs) == 7  # one CaseRun per EvaluationCase in the dataset

    by_status = {cr.status for cr in case_runs}
    assert CaseRunStatus.SUCCESS in by_status
    assert CaseRunStatus.ERROR in by_status  # the injected crash didn't abort the run

    # every case still got evaluated, including the one that crashed
    for case_run in case_runs:
        results = session.query(EvaluationResult).filter_by(case_run_id=case_run.id).all()
        assert len(results) == len(evaluators)


def test_wrong_answer_case_is_caught_as_a_regression_not_silently_passed(session):
    dataset, agent_version, evaluators = _seed_run_inputs(session)
    run = run_evaluation(
        session, agent_version_id=agent_version.id, dataset_id=dataset.id,
        evaluator_ids=[e.id for e in evaluators],
    )

    case_runs = {
        session.get(EvaluationCase, cr.evaluation_case_id).key: cr
        for cr in session.query(CaseRun).filter_by(evaluation_run_id=run.id).all()
    }
    wrong_answer_run = case_runs["simulated-wrong-answer"]
    assert wrong_answer_run.status == CaseRunStatus.SUCCESS  # the agent didn't crash...

    results = session.query(EvaluationResult).filter_by(case_run_id=wrong_answer_run.id).all()
    correctness_result = next(
        r for r in results
        if session.get(type(evaluators[0]), r.evaluator_id).dimension == "task_correctness"
    )
    assert correctness_result.passed is False  # ...but the wrong answer is still caught


class _BrokenEvaluator(Evaluator):
    key = "broken_evaluator"
    dimension = "task_correctness"

    def evaluate(self, case, execution_result):
        raise RuntimeError("evaluator is broken on purpose")


def test_one_evaluator_crashing_does_not_invalidate_other_evaluators(session, monkeypatch):
    dataset, agent_version, evaluators = _seed_run_inputs(session)
    broken = ensure_evaluator(
        session, key="broken_evaluator", version="v1",
        type=EvaluatorType.CUSTOM, dimension="task_correctness",
    )
    monkeypatch.setitem(evaluator_registry.EVALUATOR_REGISTRY, "broken_evaluator", _BrokenEvaluator)

    run = run_evaluation(
        session, agent_version_id=agent_version.id, dataset_id=dataset.id,
        evaluator_ids=[e.id for e in evaluators] + [broken.id],
    )

    assert run.status == RunStatus.COMPLETED_WITH_ERRORS
    case_runs = session.query(CaseRun).filter_by(evaluation_run_id=run.id).all()
    for case_run in case_runs:
        results = {
            r.evaluator_id: r
            for r in session.query(EvaluationResult).filter_by(case_run_id=case_run.id).all()
        }
        # the broken evaluator's failure is recorded...
        assert broken.id in results
        assert "raised" in results[broken.id].reasoning
        # ...but every other evaluator still produced a real result for this case
        for evaluator in evaluators:
            assert evaluator.id in results
            assert "raised" not in (results[evaluator.id].reasoning or "")
