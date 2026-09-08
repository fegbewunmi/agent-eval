from collections import Counter

from app.evaluators.base import Evaluator, EvaluatorResult
from app.models.dataset import EvaluationCase
from app.schemas.execution_result import AgentExecutionResult


class NoRedundantToolCalls(Evaluator):
    """Did the agent call the same specialist more than once in one investigation?
    Needs no case-specific configuration - it's a general efficiency check over whatever
    trace the agent produced. docs/evaluation-methodology.md "tool efficiency"."""

    key = "no_redundant_tool_calls"
    dimension = "tool_efficiency"

    def evaluate(
        self, case: EvaluationCase, execution_result: AgentExecutionResult
    ) -> list[EvaluatorResult]:
        counts = Counter(tool_call.tool_name for tool_call in execution_result.tool_calls)
        redundant = {name: count for name, count in counts.items() if count > 1}
        passed = not redundant
        return [
            EvaluatorResult(
                dimension=self.dimension,
                score=1.0 if passed else 0.0,
                passed=passed,
                reasoning=(
                    "No specialist was called more than once."
                    if passed
                    else f"Redundant calls: {redundant}"
                ),
                raw_output={"call_counts": dict(counts)},
            )
        ]
