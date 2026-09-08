"""Deterministic evaluators. docs/evaluation-architecture.md "deterministic evaluators" -
pure functions over execution_result and case.expected, no judgment involved.
"""

from app.evaluators.base import Evaluator, EvaluatorResult
from app.models.dataset import EvaluationCase
from app.schemas.execution_result import AgentExecutionResult


class StructuredFieldExactMatch(Evaluator):
    """Checks that specific fields of structured_output exactly match case.expected.

    case.expected shape consumed by this evaluator:
        {"structured_output": {"<field>": <expected value>, ...}}
    Only the fields listed under "structured_output" are checked; unlisted fields in the
    agent's actual output are ignored.
    """

    key = "structured_field_exact_match"
    dimension = "task_correctness"

    def evaluate(
        self, case: EvaluationCase, execution_result: AgentExecutionResult
    ) -> list[EvaluatorResult]:
        expected_fields = case.expected.get("structured_output", {})
        if not expected_fields:
            return [
                EvaluatorResult(
                    dimension=self.dimension,
                    score=0.0,
                    passed=None,
                    reasoning="No expected structured_output fields configured for this case.",
                )
            ]

        actual = execution_result.structured_output or {}
        mismatches = {
            field: {"expected": expected, "actual": actual.get(field)}
            for field, expected in expected_fields.items()
            if actual.get(field) != expected
        }

        passed = not mismatches
        return [
            EvaluatorResult(
                dimension=self.dimension,
                score=1.0 if passed else 0.0,
                passed=passed,
                reasoning=(
                    "All expected fields matched."
                    if passed
                    else f"Mismatched fields: {mismatches}"
                ),
                raw_output={"mismatches": mismatches},
            )
        ]
