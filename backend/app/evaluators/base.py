"""Evaluator interface. docs/evaluation-architecture.md, ADR-0002.

All evaluator categories (deterministic, rule_based, llm_judge, custom) share this one
interface; the runner invokes every evaluator identically regardless of category.
"""

from abc import ABC, abstractmethod

from app.models.dataset import EvaluationCase
from app.schemas.execution_result import AgentExecutionResult


class EvaluatorResult:
    """What an Evaluator.evaluate() call produces for one dimension."""

    def __init__(self, dimension: str, score: float, passed: bool | None = None,
                 reasoning: str | None = None, raw_output: dict | None = None) -> None:
        self.dimension = dimension
        self.score = score
        self.passed = passed
        self.reasoning = reasoning
        self.raw_output = raw_output or {}


class Evaluator(ABC):
    key: str
    dimension: str

    def __init__(self, config: dict | None = None) -> None:
        """`config` is the Evaluator DB row's own config (docs/domain-model.md), analogous
        to AgentVersion.config for adapters — thresholds for deterministic/rule-based
        evaluators (which have mostly used case.expected instead so far), or judge
        model/project/temperature for llm_judge evaluators, which is genuinely
        evaluator-level rather than case-level. Added in Phase 3 when the first llm_judge
        evaluator needed it; deterministic/rule-based evaluators are free to ignore it.
        """
        self.config = config or {}

    @abstractmethod
    def evaluate(
        self,
        case: EvaluationCase,
        execution_result: AgentExecutionResult,
    ) -> list[EvaluatorResult]:
        """Score one CaseRun's execution result. May return >1 result only when a single
        pass naturally produces more than one dimension (discouraged — see
        docs/evaluation-architecture.md)."""
        raise NotImplementedError
