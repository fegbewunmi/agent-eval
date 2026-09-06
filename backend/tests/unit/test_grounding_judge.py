"""Unit tests for the grounding LLM-judge evaluator, against a fake judge client — no
live Vertex AI calls here (docs/tech-stack.md: tests shouldn't depend on external infra or
incur LLM cost). The client is injected directly, same pattern as mocking the incident
investigator's HTTP transport in test_incident_investigator_adapter.py. Live-call proof is
in docs/phase-notes/phase-3.md, not in the automated suite.
"""

from app.evaluators.llm_judge.client import JudgeCallError
from app.evaluators.llm_judge.grounding import GroundingJudge
from app.schemas.execution_result import AgentExecutionResult, ToolCallRecord


class FakeCase:
    expected = {}


class FakeJudgeClient:
    def __init__(self, response: dict | None = None, raises: Exception | None = None):
        self.response = response
        self.raises = raises
        self.last_prompt: str | None = None
        self.last_temperature: float | None = None

    def generate_json(self, prompt: str, *, temperature: float = 0.0) -> dict:
        self.last_prompt = prompt
        self.last_temperature = temperature
        if self.raises:
            raise self.raises
        return self.response


def _result(structured_output=None, tool_calls=None):
    return AgentExecutionResult(
        status="success", latency_ms=10.0,
        structured_output=structured_output or {},
        tool_calls=tool_calls or [],
    )


def test_all_claims_grounded_passes():
    client = FakeJudgeClient(response={"ungrounded_claims": [], "reasoning": "All claims match the evidence."})
    judge = GroundingJudge(config={}, client=client)
    result = _result(
        structured_output={"supporting_evidence": ["deployment 15 min before onset"]},
        tool_calls=[ToolCallRecord(sequence_index=0, tool_name="deployment_agent", arguments={}, status="success",
                                    result={"deployments": ["v2.3.1 at 05:45"]})],
    )

    evaluated = judge.evaluate(FakeCase(), result)[0]
    assert evaluated.passed is True
    assert evaluated.score == 1.0
    assert "match the evidence" in evaluated.reasoning


def test_some_claims_ungrounded_fails_with_partial_score():
    client = FakeJudgeClient(response={
        "ungrounded_claims": ["a fabricated claim not in any evidence"],
        "reasoning": "One claim has no basis in the gathered evidence.",
    })
    judge = GroundingJudge(config={}, client=client)
    result = _result(
        structured_output={"supporting_evidence": ["real claim", "a fabricated claim not in any evidence"]},
        tool_calls=[ToolCallRecord(sequence_index=0, tool_name="telemetry_agent", arguments={}, status="success",
                                    result={"summary": "error spike confirmed"})],
    )

    evaluated = judge.evaluate(FakeCase(), result)[0]
    assert evaluated.passed is False
    assert evaluated.score == 0.5
    assert evaluated.raw_output["ungrounded_claims"] == ["a fabricated claim not in any evidence"]


def test_no_supporting_evidence_is_not_applicable():
    judge = GroundingJudge(config={}, client=FakeJudgeClient(response={}))
    result = _result(structured_output={"root_cause_category": "deployment"})

    evaluated = judge.evaluate(FakeCase(), result)[0]
    assert evaluated.passed is None
    assert "No supporting_evidence" in evaluated.reasoning


def test_temperature_zero_is_the_default_mitigation():
    client = FakeJudgeClient(response={"ungrounded_claims": [], "reasoning": "ok"})
    judge = GroundingJudge(config={}, client=client)
    result = _result(
        structured_output={"supporting_evidence": ["claim"]},
        tool_calls=[ToolCallRecord(sequence_index=0, tool_name="x", arguments={}, status="success", result={"a": 1})],
    )
    judge.evaluate(FakeCase(), result)
    assert client.last_temperature == 0.0  # docs/evaluation-architecture.md's required mitigation


def test_judge_call_error_propagates_for_runner_isolation():
    client = FakeJudgeClient(raises=JudgeCallError("boom"))
    judge = GroundingJudge(config={}, client=client)
    result = _result(
        structured_output={"supporting_evidence": ["claim"]},
        tool_calls=[ToolCallRecord(sequence_index=0, tool_name="x", arguments={}, status="success", result={"a": 1})],
    )
    try:
        judge.evaluate(FakeCase(), result)
        assert False, "expected JudgeCallError to propagate"
    except JudgeCallError:
        pass
