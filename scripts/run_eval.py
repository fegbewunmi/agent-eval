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

DEFAULT_EVALUATORS = [
    dict(key="structured_field_exact_match", version="v1", type=EvaluatorType.DETERMINISTIC,
         dimension="task_correctness"),
    dict(key="completion_check", version="v1", type=EvaluatorType.DETERMINISTIC,
         dimension="completion"),
    dict(key="latency_threshold", version="v1", type=EvaluatorType.DETERMINISTIC,
         dimension="latency"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-file", required=True)
    parser.add_argument("--agent-name", default="stub-agent")
    parser.add_argument("--adapter-key", default="stub-agent")
    parser.add_argument("--agent-version", default="v1")
    parser.add_argument("--agent-config", default="{}", help="JSON config for the agent version")
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
        evaluators = [ensure_evaluator(session, **spec) for spec in DEFAULT_EVALUATORS]
        session.commit()

        run = run_evaluation(
            session,
            agent_version_id=agent_version.id,
            dataset_id=dataset.id,
            evaluator_ids=[e.id for e in evaluators],
            triggered_by="cli:run_eval.py",
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

    print(f"\n{'case':38} {'status':10} {'latency_ms':>10}")
    for cr in sorted(case_runs, key=lambda c: c.created_at):
        case = session.get(EvaluationCase, cr.evaluation_case_id)
        print(f"{case.key:38} {cr.status.value:10} {cr.latency_ms:>10.1f}")
        for result in session.query(EvaluationResult).filter_by(case_run_id=cr.id).all():
            evaluator = session.get(Evaluator, result.evaluator_id)
            mark = "PASS" if result.passed else ("FAIL" if result.passed is False else "n/a")
            print(f"    [{evaluator.dimension:16}] {mark:4}  {result.reasoning}")
            dimension_stats[evaluator.dimension].append(float(result.score))

    print("\nPer-dimension summary:")
    for dimension, scores in sorted(dimension_stats.items()):
        mean_score = sum(scores) / len(scores)
        print(f"  {dimension:16} mean_score={mean_score:.2f}  n={len(scores)}")


if __name__ == "__main__":
    main()
