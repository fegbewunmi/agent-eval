"""Unit tests for the real Incident Investigation Platform adapter, against a mocked HTTP
transport shaped exactly like the target system's real API responses (verified by hand
against a live instance - see docs/phase-notes/phase-2.md). No live GCP/Vertex AI/Cloud
SQL calls happen in this test file; that's deliberate (docs/tech-stack.md - tests shouldn't
depend on external infra or incur LLM cost), and is a separate concern from the adapter's
correctness, which these tests do cover.
"""

import httpx
import pytest

from app.adapters.incident_investigator.adapter import IncidentInvestigatorAdapter

INVESTIGATION_ID = "11111111-1111-1111-1111-111111111111"
BASE_URL = "http://testserver"


def _status_payload(phase: str) -> dict:
    return {
        "investigation_id": INVESTIGATION_ID,
        "incident": {
            "incident_id": "INC-FD-001", "alert_name": "HighErrorRate", "severity": "P1",
            "service_name": "payments", "onset_timestamp": "2026-08-06T06:00:00Z",
            "description": "...", "alert_metadata": {},
        },
        "phase": phase,
        "working_hypothesis": "deployment v2.3.1 likely culprit",
        "working_confidence": 85.0,
        "iterations_used": 4,
        "tool_calls_used": 3,
        "started_at": "2026-08-06T06:01:00Z",
        "completed_at": "2026-08-06T06:02:00Z" if phase in ("complete", "escalated") else None,
    }


_FINDINGS_PAYLOAD = {
    "incident_id": "INC-FD-001",
    "investigation_summary": "Deployment v2.3.1 caused the error spike.",
    "timeline": [],
    "hypotheses": [],
    "top_hypothesis": {
        "hypothesis_id": "h1", "description": "...", "root_cause_category": "deployment",
        "affected_service": "payments", "confidence_pct": 95.0,
        "supporting_evidence": ["deployment 15 min before onset"], "contradicting_evidence": [],
        "recommended_action": "roll back to v2.3.0", "authority_level": "L2",
    },
    "investigation_incomplete": False, "requires_escalation": False, "escalation_reason": None,
    "incident_memory_record": None,
}

_TIMELINE_PAYLOAD = {
    "investigation_id": INVESTIGATION_ID,
    "events": [
        {"timestamp": "2026-08-06T06:01:00Z", "event_type": "investigation_finding", "service": "payments",
         "description": "Planner: invoke telemetry", "source": "planner", "evidence_ref": None},
        {"timestamp": "2026-08-06T06:01:05Z", "event_type": "investigation_finding", "service": "payments",
         "description": "Telemetry check complete", "source": "telemetry_agent", "evidence_ref": None},
        {"timestamp": "2026-08-06T06:01:20Z", "event_type": "action_dispatched", "service": "payments",
         "description": "Slack message sent", "source": "action_dispatcher", "evidence_ref": None},
    ],
}

_EVIDENCE_PAYLOAD = {
    "investigation_id": INVESTIGATION_ID,
    "telemetry_findings": [
        {"service": "payments", "time_window": {"start": "2026-08-06T05:30:00Z", "end": "2026-08-06T06:30:00Z"},
         "query": "high error rate", "key_metrics": [], "anomalous_metrics": [], "log_events": [],
         "resource_utilization": {}, "error_rate_change_pct": 40.0, "latency_p99_change_pct": 1400.0,
         "summary": "error spike confirmed", "error": None},
    ],
    "deployment_findings": [],
    "knowledge_context": [],
    "service_topology": None,
}

_ANALYSIS_PAYLOAD = {
    "investigation_id": INVESTIGATION_ID,
    "analysis_output": None,
    "validation_result": {"passed": True, "issues": [], "confidence_ok": True, "evidence_grounded": True,
                           "sources_aligned": True, "authority_ok": True, "risk_level": "L2",
                           "investigation_incomplete": False},
    "token_log": [
        {"node": "planner", "input_tokens": 600, "output_tokens": 400, "cost_usd": 0.0002},
        {"node": "telemetry", "input_tokens": 300, "output_tokens": 500, "cost_usd": 0.00017},
    ],
    "budget": {"max_iterations": 7, "max_tool_calls": 28, "max_tokens": 50000, "max_latency_seconds": 30.0,
               "confidence_threshold": 0.8, "iterations_used": 4, "tool_calls_used": 3,
               "input_tokens_used": 900, "output_tokens_used": 900, "elapsed_seconds": 60.0},
    "human_feedback": [], "pending_approvals": [], "dispatched_actions": [],
}


def _handler_factory(phase_sequence: list[str], findings_status: int = 200):
    state = {"status_calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path == "/v1/investigations/replay/INC-FD-001":
            return httpx.Response(202, json={"investigation_id": INVESTIGATION_ID, "status": "accepted", "message": "..."})
        if request.method == "GET" and path == f"/v1/investigations/{INVESTIGATION_ID}/status":
            idx = min(state["status_calls"], len(phase_sequence) - 1)
            state["status_calls"] += 1
            phase = phase_sequence[idx]
            if phase == "404":
                return httpx.Response(404, json={"detail": "Investigation not found"})
            return httpx.Response(200, json=_status_payload(phase))
        if path == f"/v1/investigations/{INVESTIGATION_ID}/findings":
            if findings_status != 200:
                return httpx.Response(findings_status, json={"detail": "synthesis not yet complete"})
            return httpx.Response(200, json=_FINDINGS_PAYLOAD)
        if path == f"/v1/investigations/{INVESTIGATION_ID}/timeline":
            return httpx.Response(200, json=_TIMELINE_PAYLOAD)
        if path == f"/v1/investigations/{INVESTIGATION_ID}/evidence":
            return httpx.Response(200, json=_EVIDENCE_PAYLOAD)
        if path == f"/v1/investigations/{INVESTIGATION_ID}/analysis":
            return httpx.Response(200, json=_ANALYSIS_PAYLOAD)
        raise AssertionError(f"unexpected request: {request.method} {path}")

    return handler


def _patch_client(monkeypatch, handler) -> None:
    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr("app.adapters.incident_investigator.adapter.httpx.Client", fake_client)


def test_execute_success_maps_synthesis_trace_and_tokens(monkeypatch):
    _patch_client(monkeypatch, _handler_factory(["investigating", "complete"]))

    result = IncidentInvestigatorAdapter().execute(
        {"fixture_id": "INC-FD-001"},
        {"base_url": BASE_URL, "poll_interval_seconds": 0},
    )

    assert result.status == "success"
    assert result.structured_output["root_cause_category"] == "deployment"
    assert result.structured_output["affected_service"] == "payments"
    assert result.structured_output["confidence_pct"] == 95.0
    assert "v2.3.1" in result.final_output

    assert len(result.trace) == 3
    assert result.trace[0].step_type == "reasoning"  # source=planner
    assert result.trace[1].step_type == "tool_call"  # source=telemetry_agent
    assert result.trace[2].step_type == "handoff"    # source=action_dispatcher

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "telemetry_agent"

    assert result.token_usage.prompt_tokens == 900
    assert result.token_usage.completion_tokens == 900
    assert result.cost_usd == pytest.approx(0.00037)
    assert result.latency_ms > 0  # measured wall-clock, not the target's self-reported elapsed time


def test_execute_treats_escalated_as_success_with_escalation_flagged(monkeypatch):
    _patch_client(monkeypatch, _handler_factory(["investigating", "escalated"], findings_status=409))

    result = IncidentInvestigatorAdapter().execute(
        {"fixture_id": "INC-FD-001"},
        {"base_url": BASE_URL, "poll_interval_seconds": 0},
    )

    assert result.status == "success"  # the graph finished; escalation is a business outcome, not a crash
    assert result.structured_output["requires_escalation"] is True
    assert result.structured_output["root_cause_category"] is None


def test_execute_survives_404_race_right_after_starting(monkeypatch):
    """POST /replay(...) returns 202 and starts the graph via asyncio.create_task on the
    target system's side, so the very first GET .../status can 404 before the background
    task's first checkpoint write lands - observed against a live instance
    (docs/phase-notes/phase-2.md). This must be tolerated like a non-terminal phase, not
    treated as a hard failure."""
    _patch_client(monkeypatch, _handler_factory(["404", "404", "investigating", "complete"]))

    result = IncidentInvestigatorAdapter().execute(
        {"fixture_id": "INC-FD-001"},
        {"base_url": BASE_URL, "poll_interval_seconds": 0},
    )

    assert result.status == "success"
    assert result.structured_output["root_cause_category"] == "deployment"


def test_execute_times_out_when_never_terminal(monkeypatch):
    _patch_client(monkeypatch, _handler_factory(["investigating", "investigating", "investigating"]))

    result = IncidentInvestigatorAdapter().execute(
        {"fixture_id": "INC-FD-001"},
        {"base_url": BASE_URL, "poll_interval_seconds": 0, "max_wait_seconds": 0.05},
    )

    assert result.status == "timeout"
    assert result.error is not None


def test_execute_normalizes_http_errors_to_status_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Unknown fixture"})

    _patch_client(monkeypatch, handler)

    result = IncidentInvestigatorAdapter().execute(
        {"fixture_id": "does-not-exist"},
        {"base_url": BASE_URL},
    )

    assert result.status == "error"
    assert result.error is not None
