"""Rule-based evaluators over structured trace data (ToolCall records).
docs/evaluation-architecture.md "rule-based evaluators": process/procedure correctness
and tool selection, checked against the structured trace rather than free text.
"""

from app.evaluators.base import Evaluator, EvaluatorResult
from app.models.dataset import EvaluationCase
from app.schemas.execution_result import AgentExecutionResult


class RequiredToolCalls(Evaluator):
    """Did the agent call every tool the scenario requires? Answers "did it even look in
    the right places" independent of what conclusion it drew from them.

    case.expected shape consumed: {"required_tools": ["telemetry_agent", ...]}
    """

    key = "required_tool_calls"
    dimension = "tool_selection"

    def evaluate(
        self, case: EvaluationCase, execution_result: AgentExecutionResult
    ) -> list[EvaluatorResult]:
        required = set(case.expected.get("required_tools", []))
        if not required:
            return [
                EvaluatorResult(
                    dimension=self.dimension, score=0.0, passed=None,
                    reasoning="No required_tools configured for this case.",
                )
            ]

        called = {tool_call.tool_name for tool_call in execution_result.tool_calls}
        missing = required - called
        passed = not missing
        return [
            EvaluatorResult(
                dimension=self.dimension,
                score=1.0 if passed else 0.0,
                passed=passed,
                reasoning=(
                    "All required tools were called."
                    if passed
                    else f"Missing required tool calls: {sorted(missing)}"
                ),
                raw_output={"called": sorted(called), "required": sorted(required), "missing": sorted(missing)},
            )
        ]
