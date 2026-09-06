from app.evaluators.base import Evaluator, EvaluatorResult
from app.models.dataset import EvaluationCase
from app.schemas.execution_result import AgentExecutionResult


class LatencyThreshold(Evaluator):
    """Did the case complete within an acceptable latency budget?
    docs/evaluation-methodology.md "latency" — deterministic, from CaseRun.latency_ms.

    case.expected shape consumed: {"max_latency_ms": <number>} (optional; if absent this
    evaluator only reports latency, it does not fail the case).
    """

    key = "latency_threshold"
    dimension = "latency"

    def evaluate(
        self, case: EvaluationCase, execution_result: AgentExecutionResult
    ) -> list[EvaluatorResult]:
        budget = case.expected.get("max_latency_ms")
        latency = execution_result.latency_ms
        passed = latency <= budget if budget is not None else None
        return [
            EvaluatorResult(
                dimension=self.dimension,
                score=1.0 if passed is not False else 0.0,
                passed=passed,
                reasoning=(
                    f"latency_ms={latency:.1f}"
                    + (f", budget_ms={budget}" if budget is not None else " (no budget configured)")
                ),
                raw_output={"latency_ms": latency, "budget_ms": budget},
            )
        ]
