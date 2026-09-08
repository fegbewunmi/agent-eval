from app.evaluators.deterministic.text_contains import (
    FinalOutputContainsKeywords,
    RetrievedTextContainsKeywords,
)
from app.schemas.execution_result import AgentExecutionResult, ToolCallRecord


class FakeCase:
    def __init__(self, expected: dict):
        self.expected = expected


def _result(final_output=None, tool_calls=None):
    return AgentExecutionResult(
        status="success", latency_ms=10.0,
        final_output=final_output, tool_calls=tool_calls or [],
    )


def test_final_output_contains_passes_when_all_present():
    case = FakeCase({"final_output_contains": ["Bloomberg", "Texas A&M"]})
    result = _result(final_output="Worked at Bloomberg after graduating from Texas A&M.")
    evaluated = FinalOutputContainsKeywords().evaluate(case, result)[0]
    assert evaluated.passed is True


def test_final_output_contains_fails_when_missing():
    case = FakeCase({"final_output_contains": ["Bloomberg", "Google"]})
    result = _result(final_output="Worked at Bloomberg.")
    evaluated = FinalOutputContainsKeywords().evaluate(case, result)[0]
    assert evaluated.passed is False
    assert "Google" in evaluated.raw_output["missing"]


def test_final_output_contains_is_case_insensitive():
    case = FakeCase({"final_output_contains": ["bloomberg"]})
    result = _result(final_output="Worked at BLOOMBERG LP.")
    evaluated = FinalOutputContainsKeywords().evaluate(case, result)[0]
    assert evaluated.passed is True


def test_final_output_contains_not_applicable_when_unconfigured():
    case = FakeCase({})
    result = _result(final_output="anything")
    evaluated = FinalOutputContainsKeywords().evaluate(case, result)[0]
    assert evaluated.passed is None


def test_retrieved_text_contains_checks_tool_call_chunks():
    case = FakeCase({"retrieved_text_contains": ["pgvector", "Pinecone"]})
    tool_call = ToolCallRecord(
        sequence_index=0, tool_name="hybrid_retrieve", arguments={}, status="success",
        result={"chunks": [{"text": "Experience with pgvector and Pinecone."}]},
    )
    result = _result(tool_calls=[tool_call])
    evaluated = RetrievedTextContainsKeywords().evaluate(case, result)[0]
    assert evaluated.passed is True


def test_retrieved_text_contains_fails_when_relevant_chunk_never_retrieved():
    case = FakeCase({"retrieved_text_contains": ["pgvector"]})
    tool_call = ToolCallRecord(
        sequence_index=0, tool_name="hybrid_retrieve", arguments={}, status="success",
        result={"chunks": [{"text": "Unrelated content about WebSockets."}]},
    )
    result = _result(tool_calls=[tool_call])
    evaluated = RetrievedTextContainsKeywords().evaluate(case, result)[0]
    assert evaluated.passed is False
