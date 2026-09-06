#!/usr/bin/env python3
"""CLI entry point for Phase 1: run a dataset against an agent version and print a
per-dimension summary. Calls the exact same `run_evaluation(...)` that a future API
endpoint will call (docs/architecture.md — one code path for triggering a run).

Usage:
    uv run --project backend python ../scripts/run_eval.py \
        --dataset-file ../datasets/stub-agent/smoke-v1/cases.yaml \
        --agent-name stub-agent --agent-version v1
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.models.enums import EvaluatorType  # noqa: E402
from app.services.dataset_loader import load_dataset_from_file  # noqa: E402
from app.services.runner import run_evaluation  # noqa: E402
from app.services.seed import ensure_agent, ensure_agent_version, ensure_evaluator  # noqa: E402

DETERMINISTIC_EVALUATORS = [
    dict(key="structured_field_exact_match", version="v1", type=EvaluatorType.DETERMINISTIC,
         dimension="task_correctness"),
    dict(key="structured_field_minimum", version="v1", type=EvaluatorType.DETERMINISTIC,
         dimension="task_correctness"),
    dict(key="completion_check", version="v1", type=EvaluatorType.DETERMINISTIC,
         dimension="completion"),
    dict(key="latency_threshold", version="v1", type=EvaluatorType.DETERMINISTIC,
         dimension="latency"),
]

RULE_BASED_EVALUATORS = [
    dict(key="required_tool_calls", version="v1", type=EvaluatorType.RULE_BASED,
         dimension="tool_selection"),
    dict(key="no_redundant_tool_calls", version="v1", type=EvaluatorType.RULE_BASED,
         dimension="tool_efficiency"),
]

# Evaluators absent from a case's `expected` config score as "n/a" (see each evaluator's
# no-config-configured branch), so it's safe to run the full set against every adapter —
# the stub-agent dataset just won't exercise required_tool_calls/no_redundant_tool_calls
# meaningfully since its cases don't set `required_tools`.
ALL_EVALUATORS = DETERMINISTIC_EVALUATORS + RULE_BASED_EVALUATORS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-file", required=True)
    parser.add_argument("--agent-name", default="stub-agent")
    parser.add_argument("--adapter-key", default="stub-agent")
    parser.add_argument("--agent-version", default="v1")
    parser.add_argument("--agent-config", default="{}", help="JSON config for the agent version")
    parser.add_argument("--timeout-seconds", type=float, default=30.0,
                         help="Runner-enforced per-case timeout (docs/architecture.md). "
                              "The incident-investigator adapter needs 180+.")
    args = parser.parse_args()

    import json

    session = SessionLocal()
    try:
        dataset = load_dataset_from_file(session, args.dataset_file)
        agent = ensure_agent(session, name=args.agent_name, adapter_key=args.adapter_key)
        agent_version = ensure_agent_version(
            session, agent=agent, version_label=args.agent_version,
            config=json.loads(args.agent_config),
        )
        evaluators = [ensure_evaluator(session, **spec) for spec in ALL_EVALUATORS]
        session.commit()

        run = run_evaluation(
            session,
            agent_version_id=agent_version.id,
            dataset_id=dataset.id,
            evaluator_ids=[e.id for e in evaluators],
            triggered_by="cli:run_eval.py",
            timeout_seconds=args.timeout_seconds,
        )
        print_summary(session, run)
    finally:
        session.close()


def print_summary(session, run) -> None:
    from app.models.run import CaseRun, EvaluationResult
    from app.models.dataset import EvaluationCase
    from app.models.evaluator import Evaluator

    print(f"\nEvaluationRun {run.id}  status={run.status.value}")
    print(f"  agent_version_id={run.agent_version_id}  dataset_id={run.dataset_id}")
    print(f"  dataset_snapshot_hash={run.dataset_snapshot_hash[:12]}...")

    case_runs = session.query(CaseRun).filter_by(evaluation_run_id=run.id).all()
    dimension_stats: dict[str, list[float]] = defaultdict(list)
    dimension_na_counts: dict[str, int] = defaultdict(int)

    print(f"\n{'case':38} {'status':10} {'latency_ms':>10}")
    for cr in sorted(case_runs, key=lambda c: c.created_at):
        case = session.get(EvaluationCase, cr.evaluation_case_id)
        print(f"{case.key:38} {cr.status.value:10} {cr.latency_ms:>10.1f}")
        for result in session.query(EvaluationResult).filter_by(case_run_id=cr.id).all():
            evaluator = session.get(Evaluator, result.evaluator_id)
            mark = "PASS" if result.passed else ("FAIL" if result.passed is False else "n/a")
            print(f"    [{evaluator.dimension:16}] {mark:4}  {result.reasoning}")
            # passed=None means "not applicable to this case" (e.g. no expected value was
            # configured for this evaluator), not "failed" — excluded from the mean so a
            # dataset that doesn't exercise every evaluator on every case doesn't get a
            # misleadingly deflated score. docs/evaluation-methodology.md.
            if result.passed is None:
                dimension_na_counts[evaluator.dimension] += 1
            else:
                dimension_stats[evaluator.dimension].append(float(result.score))

    print("\nPer-dimension summary:")
    all_dimensions = sorted(set(dimension_stats) | set(dimension_na_counts))
    for dimension in all_dimensions:
        scores = dimension_stats[dimension]
        na = dimension_na_counts[dimension]
        if scores:
            mean_score = sum(scores) / len(scores)
            print(f"  {dimension:16} mean_score={mean_score:.2f}  n={len(scores)}  (n/a={na})")
        else:
            print(f"  {dimension:16} mean_score=n/a       n=0  (n/a={na})")


if __name__ == "__main__":
    main()
