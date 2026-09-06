"""Adapter for the AI Operations Center (github.com/fegbewunmi/ai-operations-center) —
a LangGraph multi-agent incident investigator, invoked over its HTTP API. docs/roadmap.md
Phase 2, docs/agent-integration.md.

This module is the only place in the evaluation platform allowed to know that the target
agent is LangGraph-based, calls Gemini via Vertex AI, or persists to Cloud SQL — none of
that leaks past this file, per ADR-0001.

The target system's `POST /v1/investigations` returns 202 immediately and runs the
investigation graph in the background, so `execute()` has to start it, poll
`GET .../status` until the graph reaches a terminal phase, then fetch results from the
findings/timeline/evidence/analysis endpoints. Both graph-terminal outcomes the target
system defines — "complete" and "escalated" — represent the agent finishing and producing
a defined state (see app/graph/routing.py in that repo: both are reached via the graph's
own END edge, not a crash), so both normalize to AgentExecutionResult(status="success");
whether an escalation counts as a *good* outcome is left entirely to evaluators, consistent
with how CaseRun.status only tracks execution health, not task quality (docs/domain-model.md).

Expected case_input shapes:
    {"fixture_id": "INC-FD-001"}                 -> POST /v1/investigations/replay/{id}
                                                     (deterministic: fixed evidence fixtures,
                                                     only the LLM call varies between runs)
    {"incident": {...IncidentTrigger fields...}} -> POST /v1/investigations (live)

version_config:
    {"base_url": "http://localhost:8080",        # required
     "poll_interval_seconds": 3.0,               # optional, default 3.0
     "max_wait_seconds": 180.0}                  # optional, default 180.0
"""

import time
from collections.abc import Iterable

import httpx

from app.adapters.base import AgentAdapter
from app.schemas.execution_result import (
    AgentExecutionResult,
    ExecutionError,
    TokenUsage,
    ToolCallRecord,
    TraceStep,
)

_TERMINAL_PHASES = {"complete", "escalated"}

# Maps the target system's TimelineEvent.source (see app/shared/schemas/core.py in that
# repo) to our normalized step_type envelope (docs/agent-integration.md, ADR-0006).
# Sources not listed here fall back to "other" rather than raising — new specialist or
# control-flow nodes the target system adds later degrade gracefully instead of breaking
# this adapter.
_SOURCE_TO_STEP_TYPE = {
    "planner": "reasoning",
    "incident_analysis": "reasoning",
    "safety_guard": "reasoning",
    "telemetry_agent": "tool_call",
    "deployment_agent": "tool_call",
    "knowledge_agent": "tool_call",
    "synthesizer": "message",
    "action_dispatcher": "handoff",
    "l3_approval_gate": "handoff",
}

_DEFAULT_BASE_URL = "http://localhost:8080"
_DEFAULT_POLL_INTERVAL_SECONDS = 3.0
_DEFAULT_MAX_WAIT_SECONDS = 180.0


class InvestigationTimeoutError(Exception):
    """The investigation never reached a terminal phase within max_wait_seconds."""


class IncidentInvestigatorAdapter(AgentAdapter):
    def execute(self, case_input: dict, version_config: dict) -> AgentExecutionResult:
        base_url = version_config.get("base_url", _DEFAULT_BASE_URL).rstrip("/")
        poll_interval = version_config.get("poll_interval_seconds", _DEFAULT_POLL_INTERVAL_SECONDS)
        max_wait = version_config.get("max_wait_seconds", _DEFAULT_MAX_WAIT_SECONDS)
        started = time.monotonic()

        try:
            with httpx.Client(base_url=base_url, timeout=15.0) as client:
                investigation_id = self._start(client, case_input)
                status = self._poll_until_terminal(client, investigation_id, poll_interval, max_wait)
                result = self._collect_result(client, investigation_id, status)
        except InvestigationTimeoutError as exc:
            return AgentExecutionResult(
                status="timeout",
                latency_ms=(time.monotonic() - started) * 1000,
                raw_output={},
                error=ExecutionError(type="InvestigationTimeoutError", message=str(exc)),
            )
        except Exception as exc:  # noqa: BLE001 - adapter boundary must never propagate
            return AgentExecutionResult(
                status="error",
                latency_ms=(time.monotonic() - started) * 1000,
                raw_output={},
                error=ExecutionError(type=type(exc).__name__, message=str(exc)),
            )

        # Our own measured wall-clock time, not the target system's self-reported elapsed
        # time — docs/agent-integration.md: latency_ms is always adapter-measured.
        result.latency_ms = (time.monotonic() - started) * 1000
        return result

    def _start(self, client: httpx.Client, case_input: dict) -> str:
        if "fixture_id" in case_input:
            response = client.post(f"/v1/investigations/replay/{case_input['fixture_id']}")
        else:
            response = client.post("/v1/investigations", json={"incident": case_input["incident"]})
        response.raise_for_status()
        return response.json()["investigation_id"]

    def _poll_until_terminal(
        self, client: httpx.Client, investigation_id: str, poll_interval: float, max_wait: float
    ) -> dict:
        # POST /v1/investigations(/replay/...) returns 202 and starts the graph via
        # asyncio.create_task — there's an inherent race between that response and the
        # background task's first checkpoint write, during which GET .../status 404s
        # ("Investigation not found") even though the investigation is genuinely starting.
        # Observed in practice against a live instance (docs/phase-notes/phase-2.md), not
        # a hypothetical: an early 404 is treated the same as a non-terminal phase, not as
        # a failure — it only becomes a real error if it never resolves within max_wait.
        deadline = time.monotonic() + max_wait
        while True:
            response = client.get(f"/v1/investigations/{investigation_id}/status")
            if response.status_code != 404:
                response.raise_for_status()
                status = response.json()
                if status["phase"] in _TERMINAL_PHASES:
                    return status
                phase_description = status["phase"]
            else:
                phase_description = "not yet started (404)"

            if time.monotonic() >= deadline:
                raise InvestigationTimeoutError(
                    f"investigation {investigation_id} did not reach a terminal phase "
                    f"within {max_wait}s (last phase={phase_description!r})"
                )
            time.sleep(poll_interval)

    def _collect_result(self, client: httpx.Client, investigation_id: str, status: dict) -> AgentExecutionResult:
        phase = status["phase"]

        findings_response = client.get(f"/v1/investigations/{investigation_id}/findings")
        synthesis = findings_response.json() if findings_response.status_code == 200 else None

        timeline = client.get(f"/v1/investigations/{investigation_id}/timeline").json()["events"]
        evidence = client.get(f"/v1/investigations/{investigation_id}/evidence").json()
        analysis = client.get(f"/v1/investigations/{investigation_id}/analysis").json()

        trace = self._build_trace(timeline)
        tool_calls = self._build_tool_calls(evidence)
        token_usage, cost_usd = self._aggregate_tokens(analysis.get("token_log", []))
        final_output, structured_output = self._build_output(status, synthesis)

        return AgentExecutionResult(
            status="success",
            final_output=final_output,
            structured_output=structured_output,
            latency_ms=0.0,  # overwritten by execute() with the measured wall-clock time
            token_usage=token_usage,
            cost_usd=cost_usd,
            tool_calls=tool_calls,
            trace=trace,
            raw_output={"status": status, "findings": synthesis, "analysis": analysis},
        )

    def _build_output(self, status: dict, synthesis: dict | None) -> tuple[str | None, dict]:
        top = (synthesis or {}).get("top_hypothesis")
        if top is not None:
            return synthesis["investigation_summary"], {
                "phase": status["phase"],
                "root_cause_category": top["root_cause_category"],
                "affected_service": top["affected_service"],
                "confidence_pct": top["confidence_pct"],
                "authority_level": top["authority_level"],
                "recommended_action": top["recommended_action"],
                "supporting_evidence": top["supporting_evidence"],
                "requires_escalation": synthesis.get("requires_escalation", False),
                "escalation_reason": synthesis.get("escalation_reason"),
                "investigation_incomplete": synthesis.get("investigation_incomplete", False),
            }

        # No synthesis was ever produced (e.g. escalated before incident_analysis ran) —
        # GET .../findings returns 409 in this case. Still a normal (if minimal) outcome,
        # not an adapter error: report what's known from /status and flag the gap.
        return status.get("working_hypothesis"), {
            "phase": status["phase"],
            "root_cause_category": None,
            "affected_service": None,
            "confidence_pct": status.get("working_confidence", 0.0),
            "requires_escalation": status["phase"] == "escalated",
            "escalation_reason": "Investigation ended without a synthesis output",
        }

    def _build_trace(self, events: Iterable[dict]) -> list[TraceStep]:
        return [
            TraceStep(
                step_type=_SOURCE_TO_STEP_TYPE.get(event["source"], "other"),
                timestamp=event["timestamp"],
                payload=event,
            )
            for event in events
        ]

    def _build_tool_calls(self, evidence: dict) -> list[ToolCallRecord]:
        # Specialist findings (docs/architecture.md's "tool calls" for this multi-agent
        # system) don't carry their own call-order timestamp, only a time_window they
        # queried over — sequence_index here is a fixed
        # telemetry -> deployment -> knowledge ordering, a query/display convenience, not
        # an assertion about the agent's true call order. The trace (built from the
        # timeline above) carries the real chronological order.
        specs = [
            ("telemetry_agent", evidence.get("telemetry_findings", [])),
            ("deployment_agent", evidence.get("deployment_findings", [])),
            ("knowledge_agent", evidence.get("knowledge_context", [])),
        ]
        calls: list[ToolCallRecord] = []
        for tool_name, findings in specs:
            for finding in findings:
                calls.append(
                    ToolCallRecord(
                        sequence_index=len(calls),
                        tool_name=tool_name,
                        arguments={"query": finding.get("query"), "service": finding.get("service")},
                        result={k: v for k, v in finding.items() if k not in ("query", "service")},
                        status="error" if finding.get("error") else "success",
                    )
                )
        return calls

    def _aggregate_tokens(self, token_log: list[dict]) -> tuple[TokenUsage, float]:
        input_tokens = sum(entry["input_tokens"] for entry in token_log)
        output_tokens = sum(entry["output_tokens"] for entry in token_log)
        cost_usd = sum(entry["cost_usd"] for entry in token_log)
        usage = TokenUsage(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        )
        return usage, cost_usd
