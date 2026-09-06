from app.evaluators.deterministic.completion import CompletionCheck
from app.evaluators.deterministic.exact_match import StructuredFieldExactMatch
from app.evaluators.deterministic.latency import LatencyThreshold
from app.schemas.execution_result import AgentExecutionResult, ExecutionError


class FakeCase:
    def __init__(self, expected: dict):
        self.expected = expected


def _result(**overrides):
    defaults = dict(status="success", latency_ms=10.0, structured_output={"root_cause": "disk_exhaustion"})
    defaults.update(overrides)
    return AgentExecutionResult(**defaults)


def test_exact_match_passes_when_fields_match():
    case = FakeCase({"structured_output": {"root_cause": "disk_exhaustion"}})
    results = StructuredFieldExactMatch().evaluate(case, _result())
    assert results[0].passed is True
    assert results[0].score == 1.0


def test_exact_match_fails_on_mismatch():
    case = FakeCase({"structured_output": {"root_cause": "memory_leak"}})
    results = StructuredFieldExactMatch().evaluate(case, _result())
    assert results[0].passed is False
    assert results[0].score == 0.0
    assert "root_cause" in results[0].raw_output["mismatches"]


def test_completion_check_reflects_status():
    case = FakeCase({})
    ok = CompletionCheck().evaluate(case, _result(status="success"))[0]
    assert ok.passed is True

    failed = CompletionCheck().evaluate(
        case, _result(status="error", structured_output=None, error=ExecutionError(type="RuntimeError", message="boom"))
    )[0]
    assert failed.passed is False
    assert "boom" in failed.reasoning


def test_latency_threshold_respects_budget():
    case = FakeCase({"max_latency_ms": 100})
    within_budget = LatencyThreshold().evaluate(case, _result(latency_ms=50.0))[0]
    assert within_budget.passed is True

    over_budget = LatencyThreshold().evaluate(case, _result(latency_ms=500.0))[0]
    assert over_budget.passed is False


def test_latency_threshold_without_budget_is_informational_only():
    case = FakeCase({})
    result = LatencyThreshold().evaluate(case, _result(latency_ms=9999.0))[0]
    assert result.passed is None
