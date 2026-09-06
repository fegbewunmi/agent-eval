"""Regression test for a real bug (docs/phase-notes/): `_execute_with_timeout` used
`with ThreadPoolExecutor(...) as pool:`, whose __exit__ calls `pool.shutdown(wait=True)`
on every exit path - including the timeout branch - so the function silently blocked
until the slow adapter actually finished before returning its "timeout" result. Caught
live: a real adapter call reported status="timeout" only after taking its full ~60-75s
real duration anyway, defeating the entire point of a runner-enforced timeout.

This test doesn't need a real slow agent - a fake one with time.sleep() reproduces the
exact shape of the bug: the fix must let _execute_with_timeout return at approximately
the configured timeout, not at approximately the adapter's real duration.
"""

import time

from app.adapters.base import AgentAdapter
from app.schemas.execution_result import AgentExecutionResult
from app.services.runner import _execute_with_timeout


class _SlowAdapter(AgentAdapter):
    def __init__(self, sleep_seconds: float):
        self.sleep_seconds = sleep_seconds

    def execute(self, case_input: dict, version_config: dict) -> AgentExecutionResult:
        time.sleep(self.sleep_seconds)
        return AgentExecutionResult(status="success", latency_ms=self.sleep_seconds * 1000)


def test_timeout_returns_promptly_without_waiting_for_the_slow_call_to_finish():
    adapter = _SlowAdapter(sleep_seconds=2.0)
    started = time.monotonic()

    result = _execute_with_timeout(adapter, {}, {}, timeout_seconds=0.2)

    elapsed = time.monotonic() - started
    assert result.status == "timeout"
    # Before the fix this took ~2s (the adapter's real duration) because the with-block's
    # implicit shutdown(wait=True) blocked on the still-running thread. A generous margin
    # (well under the adapter's 2s sleep) proves this function isn't waiting on it.
    assert elapsed < 1.0, f"expected a prompt return near the 0.2s timeout, took {elapsed:.2f}s"
