from app.evaluators.deterministic.structured_field_minimum import StructuredFieldMinimum
from app.evaluators.rule_based.tool_efficiency import NoRedundantToolCalls
from app.evaluators.rule_based.tool_selection import RequiredToolCalls
from app.schemas.execution_result import AgentExecutionResult, ToolCallRecord


class FakeCase:
    def __init__(self, expected: dict):
        self.expected = expected


def _tool_call(name: str, index: int = 0) -> ToolCallRecord:
    return ToolCallRecord(sequence_index=index, tool_name=name, arguments={}, status="success")


def _result(tool_calls=None, structured_output=None):
    return AgentExecutionResult(
        status="success", latency_ms=10.0,
        tool_calls=tool_calls or [], structured_output=structured_output or {},
    )


def test_required_tool_calls_passes_when_all_present():
    case = FakeCase({"required_tools": ["telemetry_agent", "deployment_agent"]})
    result = _result(tool_calls=[_tool_call("telemetry_agent"), _tool_call("deployment_agent", 1)])
    evaluated = RequiredToolCalls().evaluate(case, result)[0]
    assert evaluated.passed is True


def test_required_tool_calls_fails_when_missing():
    case = FakeCase({"required_tools": ["telemetry_agent", "knowledge_agent"]})
    result = _result(tool_calls=[_tool_call("telemetry_agent")])
    evaluated = RequiredToolCalls().evaluate(case, result)[0]
    assert evaluated.passed is False
    assert "knowledge_agent" in evaluated.raw_output["missing"]


def test_no_redundant_tool_calls_passes_when_each_called_once():
    case = FakeCase({})
    result = _result(tool_calls=[_tool_call("telemetry_agent"), _tool_call("deployment_agent", 1)])
    evaluated = NoRedundantToolCalls().evaluate(case, result)[0]
    assert evaluated.passed is True


def test_no_redundant_tool_calls_fails_on_duplicate():
    case = FakeCase({})
    result = _result(tool_calls=[_tool_call("telemetry_agent"), _tool_call("telemetry_agent", 1)])
    evaluated = NoRedundantToolCalls().evaluate(case, result)[0]
    assert evaluated.passed is False
    assert evaluated.raw_output["call_counts"]["telemetry_agent"] == 2


def test_structured_field_minimum_passes_at_or_above_floor():
    case = FakeCase({"structured_output_minimums": {"confidence_pct": 75}})
    result = _result(structured_output={"confidence_pct": 85.0})
    evaluated = StructuredFieldMinimum().evaluate(case, result)[0]
    assert evaluated.passed is True


def test_structured_field_minimum_fails_below_floor():
    case = FakeCase({"structured_output_minimums": {"confidence_pct": 75}})
    result = _result(structured_output={"confidence_pct": 40.0})
    evaluated = StructuredFieldMinimum().evaluate(case, result)[0]
    assert evaluated.passed is False
    assert evaluated.raw_output["failures"]["confidence_pct"]["actual"] == 40.0
