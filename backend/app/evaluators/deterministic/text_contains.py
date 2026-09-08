"""Deterministic substring-containment checks over free text. docs/roadmap.md Phase 5:
the Document Q&A integration exposed a concrete gap the existing deterministic evaluators
couldn't express cleanly - `structured_field_exact_match`/`structured_field_minimum` only
handle exact/numeric-threshold checks on structured fields, but a synthesized natural-
language answer is neither exact-matchable nor numeric. "Does this text mention the
expected facts" is a genuinely general-purpose check, not RAG-specific in mechanism - any
adapter whose `final_output` or `tool_calls` results carry free text can use it.
"""

from app.evaluators.base import Evaluator, EvaluatorResult
from app.models.dataset import EvaluationCase
from app.schemas.execution_result import AgentExecutionResult


def _missing(haystack: str, expected_substrings: list[str]) -> list[str]:
    haystack_lower = haystack.lower()
    return [s for s in expected_substrings if s.lower() not in haystack_lower]


class FinalOutputContainsKeywords(Evaluator):
    """Does execution_result.final_output mention every expected substring?

    case.expected shape consumed: {"final_output_contains": ["substring", ...]}
    """

    key = "final_output_contains_keywords"
    dimension = "task_correctness"

    def evaluate(
        self, case: EvaluationCase, execution_result: AgentExecutionResult
    ) -> list[EvaluatorResult]:
        expected_substrings = case.expected.get("final_output_contains", [])
        if not expected_substrings:
            return [
                EvaluatorResult(
                    dimension=self.dimension, score=0.0, passed=None,
                    reasoning="No final_output_contains configured for this case.",
                )
            ]

        missing = _missing(execution_result.final_output or "", expected_substrings)
        passed = not missing
        return [
            EvaluatorResult(
                dimension=self.dimension,
                score=1.0 if passed else 0.0,
                passed=passed,
                reasoning="All expected substrings present." if passed else f"Missing: {missing}",
                raw_output={"missing": missing},
            )
        ]


class RetrievedTextContainsKeywords(Evaluator):
    """Does the text any tool call retrieved mention every expected substring? Answers
    "did retrieval/reranking even surface the relevant passage" independent of whether
    synthesis then produced a correct final answer from it - a different failure mode
    than task_correctness, worth keeping separate (docs/evaluation-methodology.md).

    case.expected shape consumed: {"retrieved_text_contains": ["substring", ...]}
    """

    key = "retrieved_text_contains_keywords"
    dimension = "retrieval"

    def evaluate(
        self, case: EvaluationCase, execution_result: AgentExecutionResult
    ) -> list[EvaluatorResult]:
        expected_substrings = case.expected.get("retrieved_text_contains", [])
        if not expected_substrings:
            return [
                EvaluatorResult(
                    dimension=self.dimension, score=0.0, passed=None,
                    reasoning="No retrieved_text_contains configured for this case.",
                )
            ]

        texts: list[str] = []
        for tool_call in execution_result.tool_calls:
            if tool_call.result and "chunks" in tool_call.result:
                texts.extend(chunk.get("text", "") for chunk in tool_call.result["chunks"])
        haystack = " ".join(texts)

        missing = _missing(haystack, expected_substrings)
        passed = not missing
        return [
            EvaluatorResult(
                dimension=self.dimension,
                score=1.0 if passed else 0.0,
                passed=passed,
                reasoning="All expected substrings were retrieved." if passed else f"Missing: {missing}",
                raw_output={"missing": missing},
            )
        ]
