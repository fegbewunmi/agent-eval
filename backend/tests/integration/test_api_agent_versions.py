"""Tests for the one write endpoint the catalog API exposes - registering a
new AgentVersion for an existing Agent (app/api/agent_versions.py). Added
for agent-dev-platform ("Orion") to call when it publishes a real,
CI-provenanced version and needs a live, callable evaluation target
registered here."""

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app
from app.services.seed import ensure_agent


def _client(session) -> TestClient:
    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_create_agent_version_returns_201_and_persists(session):
    agent = ensure_agent(session, name="incident-investigator", adapter_key="incident-investigator")
    session.flush()
    client = _client(session)

    response = client.post(
        f"/agents/{agent.id}/versions",
        json={"version_label": "ci-abc123def456", "config": {"base_url": "https://real-deployment.example"}},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["version_label"] == "ci-abc123def456"

    listed = client.get("/agents").json()
    match = next(a for a in listed if a["id"] == str(agent.id))
    assert any(v["id"] == body["id"] for v in match["versions"])


def test_create_agent_version_is_idempotent_by_version_label(session):
    agent = ensure_agent(session, name="incident-investigator-2", adapter_key="incident-investigator")
    session.flush()
    client = _client(session)

    first = client.post(f"/agents/{agent.id}/versions", json={"version_label": "same-label", "config": {"base_url": "https://a.example"}})
    second = client.post(f"/agents/{agent.id}/versions", json={"version_label": "same-label", "config": {"base_url": "https://b.example"}})

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


def test_create_agent_version_404s_for_unknown_agent(session):
    client = _client(session)
    response = client.post(
        "/agents/00000000-0000-0000-0000-000000000000/versions",
        json={"version_label": "v1", "config": {}},
    )
    assert response.status_code == 404
