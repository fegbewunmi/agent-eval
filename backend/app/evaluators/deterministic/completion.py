from app.evaluators.base import Evaluator, EvaluatorResult
from app.models.dataset import EvaluationCase
from app.schemas.execution_result import AgentExecutionResult


class CompletionCheck(Evaluator):
    """Did the agent finish the task at all? docs/evaluation-methodology.md "completion" —
    deterministic, straight from execution status."""

    key = "completion_check"
    dimension = "completion"

    def evaluate(
        self, case: EvaluationCase, execution_result: AgentExecutionResult
    ) -> list[EvaluatorResult]:
        passed = execution_result.status == "success"
        reasoning = (
            "Execution completed successfully."
            if passed
            else f"Execution ended with status={execution_result.status!r}"
            + (f": {execution_result.error.message}" if execution_result.error else "")
        )
        return [
            EvaluatorResult(
                dimension=self.dimension,
                score=1.0 if passed else 0.0,
                passed=passed,
                reasoning=reasoning,
            )
        ]
