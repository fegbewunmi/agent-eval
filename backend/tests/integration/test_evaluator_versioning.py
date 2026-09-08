"""Confirms ADR-0008's promise end-to-end: comparing two runs that used different
versions of the same evaluator key is flagged, the same way dataset drift is flagged
(ADR-0003) - docs/roadmap.md Phase 3 exit criteria for evaluator versioning.

Uses the stub-agent dataset with the grounding_judge evaluator specifically because the
stub agent's structured_output has no `supporting_evidence` field, so GroundingJudge takes
its "not applicable" early-return path without ever calling a judge model - this test is
about version-mismatch *detection*, not about judge behavior (that's covered by
test_grounding_judge.py and the live proof in docs/phase-notes/phase-3.md), so no network
call or mocking is needed here at all.
"""

from pathlib import Path

from app.models.enums import EvaluatorType
from app.services.comparison import compare_runs
from app.services.dataset_loader import load_dataset_from_file
from app.services.runner import run_evaluation
from app.services.seed import ensure_agent, ensure_agent_version, ensure_evaluator

DATASET_FILE = Path(__file__).resolve().parents[3] / "datasets" / "stub-agent" / "smoke-v1" / "cases.yaml"


def test_comparison_flags_evaluator_version_mismatch(session):
    dataset = load_dataset_from_file(session, DATASET_FILE)
    agent = ensure_agent(session, name="stub-agent", adapter_key="stub-agent")
    agent_version = ensure_agent_version(session, agent=agent, version_label="v1", config={})

    judge_v1 = ensure_evaluator(
        session, key="grounding_judge", version="v1", type=EvaluatorType.LLM_JUDGE,
        dimension="grounding", config={"project_id": "unused", "model": "gemini-2.5-flash"},
    )
    judge_v2 = ensure_evaluator(
        session, key="grounding_judge", version="v2", type=EvaluatorType.LLM_JUDGE,
        dimension="grounding", config={"project_id": "unused", "model": "gemini-2.5-pro"},
    )
    session.flush()

    run_a = run_evaluation(session, agent_version_id=agent_version.id, dataset_id=dataset.id,
                            evaluator_ids=[judge_v1.id])
    run_b = run_evaluation(session, agent_version_id=agent_version.id, dataset_id=dataset.id,
                            evaluator_ids=[judge_v2.id])

    result = compare_runs(session, run_a.id, run_b.id)

    assert len(result.evaluator_version_mismatches) == 1
    mismatch = result.evaluator_version_mismatches[0]
    assert mismatch.dimension == "grounding"
    assert mismatch.evaluator_key == "grounding_judge"
    assert mismatch.run_a_version == "v1"
    assert mismatch.run_b_version == "v2"
