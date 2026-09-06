"""API-level tests for the Phase 2 endpoints (docs/roadmap.md), against the stub-agent
adapter — deliberately no live GCP/incident-investigator calls here (docs/tech-stack.md).
Uses the same DB-per-test-transaction fixture as the runner integration tests, with the
app's dependency override pointed at that same session so requests see uncommitted data.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app
from app.models.enums import EvaluatorType
from app.services.dataset_loader import load_dataset_from_file
from app.services.seed import ensure_agent, ensure_agent_version, ensure_evaluator

DATASET_FILE = Path(__file__).resolve().parents[3] / "datasets" / "stub-agent" / "smoke-v1" / "cases.yaml"


def _seed(session):
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


def _client(session) -> TestClient:
    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_trigger_run_and_fetch_summary(session):
    dataset, agent_version, evaluators = _seed(session)
    client = _client(session)

    response = client.post("/runs", json={
        "agent_version_id": str(agent_version.id),
        "dataset_id": str(dataset.id),
        "evaluator_ids": [str(e.id) for e in evaluators],
    })
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed_with_errors"  # dataset includes injected failures
    assert len(body["case_runs"]) == 7

    fetched = client.get(f"/runs/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_get_case_run_detail(session):
    dataset, agent_version, evaluators = _seed(session)
    client = _client(session)

    run = client.post("/runs", json={
        "agent_version_id": str(agent_version.id),
        "dataset_id": str(dataset.id),
        "evaluator_ids": [str(e.id) for e in evaluators],
    }).json()

    wrong_answer_case = next(c for c in run["case_runs"] if c["case_key"] == "simulated-wrong-answer")
    detail = client.get(f"/runs/{run['id']}/cases/{wrong_answer_case['case_run_id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["case_key"] == "simulated-wrong-answer"
    correctness = next(r for r in body["evaluation_results"] if r["dimension"] == "task_correctness")
    assert correctness["passed"] is False


def test_get_run_404_for_unknown_id(session):
    client = _client(session)
    response = client.get("/runs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_compare_two_runs_detects_regression(session):
    dataset, agent_version, evaluators = _seed(session)
    client = _client(session)

    run_a = client.post("/runs", json={
        "agent_version_id": str(agent_version.id),
        "dataset_id": str(dataset.id),
        "evaluator_ids": [str(e.id) for e in evaluators],
    }).json()
    run_b = client.post("/runs", json={
        "agent_version_id": str(agent_version.id),
        "dataset_id": str(dataset.id),
        "evaluator_ids": [str(e.id) for e in evaluators],
    }).json()

    response = client.get("/runs/compare", params={"run_a_id": run_a["id"], "run_b_id": run_b["id"]})
    assert response.status_code == 200
    body = response.json()
    assert body["dataset_drift_detected"] is False
    # identical agent version + dataset run twice -> no regressions or improvements
    assert body["regressions"] == []
    assert body["improvements"] == []


def test_compare_rejects_different_datasets(session):
    dataset, agent_version, evaluators = _seed(session)
    client = _client(session)

    run_a = client.post("/runs", json={
        "agent_version_id": str(agent_version.id),
        "dataset_id": str(dataset.id),
        "evaluator_ids": [str(e.id) for e in evaluators],
    }).json()

    other_dataset = load_dataset_from_file(
        session,
        Path(__file__).resolve().parents[3] / "datasets" / "incident-investigator" / "smoke-v1" / "cases.yaml",
    )
    other_agent = ensure_agent(session, name="incident-investigator", adapter_key="incident-investigator")
    other_version = ensure_agent_version(
        session, agent=other_agent, version_label="v1",
        config={"base_url": "http://localhost:1"},  # nothing listens here -> fast, deterministic connection refusal
    )
    session.flush()

    # deliberately create a second run against a different dataset by hand rather than
    # triggering a real incident-investigator run in a unit test
    from app.services.runner import run_evaluation
    run_b = run_evaluation(
        session, agent_version_id=other_version.id, dataset_id=other_dataset.id,
        evaluator_ids=[evaluators[0].id],
    )

    response = client.get("/runs/compare", params={"run_a_id": run_a["id"], "run_b_id": str(run_b.id)})
    assert response.status_code == 400
