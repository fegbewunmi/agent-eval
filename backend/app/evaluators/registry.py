"""In-process evaluator registry, mirroring app/adapters/registry.py.

An Evaluator *instance* here corresponds to the logic behind one or more `Evaluator` DB
rows (key, version) — see ADR-0008. The DB row is what a run actually references; this
registry is how the runner resolves that row's key to executable code.
"""

from app.evaluators.base import Evaluator
from app.evaluators.deterministic.completion import CompletionCheck
from app.evaluators.deterministic.exact_match import StructuredFieldExactMatch
from app.evaluators.deterministic.latency import LatencyThreshold
from app.evaluators.deterministic.structured_field_minimum import StructuredFieldMinimum
from app.evaluators.llm_judge.grounding import GroundingJudge
from app.evaluators.rule_based.tool_efficiency import NoRedundantToolCalls
from app.evaluators.rule_based.tool_selection import RequiredToolCalls

EVALUATOR_REGISTRY: dict[str, type[Evaluator]] = {
    "structured_field_exact_match": StructuredFieldExactMatch,
    "completion_check": CompletionCheck,
    "latency_threshold": LatencyThreshold,
    "structured_field_minimum": StructuredFieldMinimum,
    "required_tool_calls": RequiredToolCalls,
    "no_redundant_tool_calls": NoRedundantToolCalls,
    "grounding_judge": GroundingJudge,
    # future: custom/* when a concrete need for it shows up
}


def get_evaluator(key: str, config: dict | None = None) -> Evaluator:
    try:
        evaluator_cls = EVALUATOR_REGISTRY[key]
    except KeyError as exc:
        raise ValueError(
            f"No evaluator registered for key={key!r}. Known evaluators: {sorted(EVALUATOR_REGISTRY)}"
        ) from exc
    return evaluator_cls(config=config)
