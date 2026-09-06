"""Stub agent adapter — a deterministic fake "incident investigator" used to validate the
platform itself (runner, schema, evaluators, failure isolation) before the real Incident
Investigation Platform adapter is built in Phase 2. See docs/roadmap.md Phase 1.

Expected case_input shape (documented for this adapter only; the platform doesn't
prescribe one — see docs/agent-integration.md):

    {"alert": "<free text alert>", "hosts": ["host-1", ...]}

Two fields are read by this adapter (and this adapter only) to deliberately exercise the
runner's failure isolation end to end, without needing any change to the AgentAdapter
interface itself:

    {"inject_failure": "error"}         -> adapter raises, runner records status="error"
    {"inject_failure": "wrong_answer"}  -> adapter returns a wrong root cause (a
                                            "regression" the agent produced, not a crash)

version_config carries agent-version-level settings only (e.g. a model name in a real
adapter); the stub agent doesn't currently use it, but it's threaded through per the
interface contract.
"""

import time
from datetime import datetime, timezone

from app.adapters.base import AgentAdapter
from app.schemas.execution_result import (
    AgentExecutionResult,
    ExecutionError,
    ToolCallRecord,
    TraceStep,
)

_ROOT_CAUSE_KEYWORDS = {
    "disk": "disk_exhaustion",
    "memory": "memory_leak",
    "cpu": "cpu_spike",
    "network": "network_partition",
}


class StubAgentAdapter(AgentAdapter):
    def execute(self, case_input: dict, version_config: dict) -> AgentExecutionResult:
        started = time.perf_counter()

        try:
            if case_input.get("inject_failure") == "error":
                raise RuntimeError("simulated agent failure (inject_failure=error)")

            result = self._investigate(case_input, version_config)
            latency_ms = (time.perf_counter() - started) * 1000
            return AgentExecutionResult(
                status="success",
                final_output=result["final_output"],
                structured_output=result["structured_output"],
                latency_ms=latency_ms,
                token_usage=None,
                cost_usd=None,
                tool_calls=result["tool_calls"],
                trace=result["trace"],
                raw_output=result["structured_output"],
            )
        except Exception as exc:  # noqa: BLE001 - adapter boundary must never propagate
            latency_ms = (time.perf_counter() - started) * 1000
            return AgentExecutionResult(
                status="error",
                latency_ms=latency_ms,
                raw_output={},
                error=ExecutionError(type=type(exc).__name__, message=str(exc)),
            )

    def _investigate(self, case_input: dict, version_config: dict) -> dict:
        alert = case_input.get("alert", "")
        hosts = case_input.get("hosts", [])
        now = datetime.now(timezone.utc)

        tool_calls = [
            ToolCallRecord(
                sequence_index=0,
                tool_name="fetch_metrics",
                arguments={"hosts": hosts},
                result={"cpu_pct": 40, "mem_pct": 55, "disk_pct": 96},
                status="success",
                latency_ms=12.0,
                started_at=now,
            ),
            ToolCallRecord(
                sequence_index=1,
                tool_name="fetch_logs",
                arguments={"hosts": hosts},
                result={"lines": [alert]},
                status="success",
                latency_ms=18.0,
                started_at=now,
            ),
        ]
        trace = [
            TraceStep(step_type="tool_call", timestamp=now, payload=tool_calls[0].model_dump(mode="json")),
            TraceStep(step_type="tool_call", timestamp=now, payload=tool_calls[1].model_dump(mode="json")),
            TraceStep(step_type="reasoning", timestamp=now, payload={"note": "matched alert keyword to root cause"}),
        ]

        root_cause = "unknown"
        for keyword, cause in _ROOT_CAUSE_KEYWORDS.items():
            if keyword in alert.lower():
                root_cause = cause
                break

        if case_input.get("inject_failure") == "wrong_answer":
            root_cause = "unknown"

        structured_output = {"root_cause": root_cause, "hosts": hosts, "confidence": 0.9}
        final_output = f"Root cause: {root_cause}. Affected hosts: {', '.join(hosts) or 'none'}."

        return {
            "final_output": final_output,
            "structured_output": structured_output,
            "tool_calls": tool_calls,
            "trace": trace,
        }
