"""Tests for the read-only catalog endpoints (docs/roadmap.md Phase 4) - browsing only,
no create/update/delete (ADR-0003, docs/phase-notes/phase-2.md)."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app
from app.models.enums import EvaluatorType
from app.services.dataset_loader import load_dataset_from_file
from app.services.seed import ensure_agent, ensure_agent_version, ensure_evaluator

DATASET_FILE = Path(__file__).resolve().parents[3] / "datasets" / "stub-agent" / "smoke-v1" / "cases.yaml"


def _client(session) -> TestClient:
    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _seed(session):
    dataset = load_dataset_from_file(session, DATASET_FILE)
    agent = ensure_agent(session, name="stub-agent", adapter_key="stub-agent")
    agent_version = ensure_agent_version(session, agent=agent, version_label="v1", config={})
    evaluator = ensure_evaluator(session, key="completion_check", version="v1",
                                  type=EvaluatorType.DETERMINISTIC, dimension="completion")
    session.flush()
    return dataset, agent, agent_version, evaluator


def test_list_agents_includes_versions(session):
    dataset, agent, agent_version, evaluator = _seed(session)
    client = _client(session)

    response = client.get("/agents")
    assert response.status_code == 200
    agents = response.json()
    stub = next(a for a in agents if a["name"] == "stub-agent")
    assert stub["adapter_key"] == "stub-agent"
    assert any(v["id"] == str(agent_version.id) for v in stub["versions"])


def test_list_datasets_reports_case_count(session):
    dataset, *_ = _seed(session)
    client = _client(session)

    response = client.get("/datasets")
    assert response.status_code == 200
    listed = next(d for d in response.json() if d["id"] == str(dataset.id))
    assert listed["case_count"] == 7


def test_get_dataset_detail_lists_cases_with_tags(session):
    dataset, *_ = _seed(session)
    client = _client(session)

    response = client.get(f"/datasets/{dataset.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["case_count"] == 7
    wrong_answer = next(c for c in body["cases"] if c["key"] == "simulated-wrong-answer")
    assert "failure-injection" in wrong_answer["tags"]


def test_get_dataset_404_for_unknown_id(session):
    client = _client(session)
    response = client.get("/datasets/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_list_evaluators(session):
    dataset, agent, agent_version, evaluator = _seed(session)
    client = _client(session)

    response = client.get("/evaluators")
    assert response.status_code == 200
    listed = next(e for e in response.json() if e["id"] == str(evaluator.id))
    assert listed["key"] == "completion_check"
    assert listed["dimension"] == "completion"


def test_list_runs_reflects_triggered_runs(session):
    dataset, agent, agent_version, evaluator = _seed(session)
    client = _client(session)

    triggered = client.post("/runs", json={
        "agent_version_id": str(agent_version.id),
        "dataset_id": str(dataset.id),
        "evaluator_ids": [str(evaluator.id)],
    }).json()

    response = client.get("/runs", params={"dataset_id": str(dataset.id)})
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()]
    assert triggered["id"] in ids
