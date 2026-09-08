from app.evaluators.base import Evaluator, EvaluatorResult
from app.models.dataset import EvaluationCase
from app.schemas.execution_result import AgentExecutionResult


class StructuredFieldMinimum(Evaluator):
    """Checks that numeric fields of structured_output meet a minimum value - e.g. a
    confidence score the agent must clear. Generalizes beyond confidence: any numeric
    field with a floor. docs/evaluation-architecture.md "deterministic evaluators".

    case.expected shape consumed:
        {"structured_output_minimums": {"confidence_pct": 75}}
    """

    key = "structured_field_minimum"
    dimension = "task_correctness"

    def evaluate(
        self, case: EvaluationCase, execution_result: AgentExecutionResult
    ) -> list[EvaluatorResult]:
        minimums = case.expected.get("structured_output_minimums", {})
        if not minimums:
            return [
                EvaluatorResult(
                    dimension=self.dimension, score=0.0, passed=None,
                    reasoning="No structured_output_minimums configured for this case.",
                )
            ]

        actual = execution_result.structured_output or {}
        failures = {
            field: {"minimum": minimum, "actual": actual.get(field)}
            for field, minimum in minimums.items()
            if actual.get(field) is None or actual[field] < minimum
        }
        passed = not failures
        return [
            EvaluatorResult(
                dimension=self.dimension,
                score=1.0 if passed else 0.0,
                passed=passed,
                reasoning="All minimums met." if passed else f"Below minimum: {failures}",
                raw_output={"failures": failures},
            )
        ]
