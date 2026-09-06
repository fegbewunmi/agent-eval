"""In-process evaluator registry, mirroring app/adapters/registry.py.

An Evaluator *instance* here corresponds to the logic behind one or more `Evaluator` DB
rows (key, version) — see ADR-0008. The DB row is what a run actually references; this
registry is how the runner resolves that row's key to executable code.
"""

from app.evaluators.base import Evaluator
from app.evaluators.deterministic.completion import CompletionCheck
from app.evaluators.deterministic.exact_match import StructuredFieldExactMatch
from app.evaluators.deterministic.latency import LatencyThreshold

EVALUATOR_REGISTRY: dict[str, type[Evaluator]] = {
    "structured_field_exact_match": StructuredFieldExactMatch,
    "completion_check": CompletionCheck,
    "latency_threshold": LatencyThreshold,
    # future: rule_based/*, llm_judge/*, custom/* per Phases 2-3
}


def get_evaluator(key: str) -> Evaluator:
    try:
        evaluator_cls = EVALUATOR_REGISTRY[key]
    except KeyError as exc:
        raise ValueError(
            f"No evaluator registered for key={key!r}. Known evaluators: {sorted(EVALUATOR_REGISTRY)}"
        ) from exc
    return evaluator_cls()
