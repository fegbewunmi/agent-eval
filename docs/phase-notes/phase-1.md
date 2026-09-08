# Phase 1 notes - deterministic core loop

Status: complete. This records what was actually built against the plan in
`docs/roadmap.md`, where it deviated, and how the exit criteria were verified.

## What was built

- **Backend package** at `backend/` (Python 3.12, `uv`-managed): SQLAlchemy 2.0 models for
  the full domain model in `docs/domain-model.md`, wired to PostgreSQL via Alembic. The
  initial migration (`backend/alembic/versions/`) creates all nine tables in one pass.
- **`AgentAdapter`** base interface (`backend/app/adapters/base.py`) + a registry
  (`backend/app/adapters/registry.py`), and the **stub agent adapter**
  (`backend/app/adapters/stub_agent/`) - a deterministic fake incident investigator used
  in place of the real Incident Investigation Platform, per the plan.
- **`Evaluator`** base interface (`backend/app/evaluators/base.py`) + registry, and three
  deterministic evaluators (`backend/app/evaluators/deterministic/`):
  `structured_field_exact_match` (task_correctness), `completion_check` (completion), and
  `latency_threshold` (latency) - covering three of the eight dimensions in
  `docs/evaluation-methodology.md`; the rest require rule-based or LLM-judge evaluators
  and are correctly deferred to Phase 2/3.
- **The runner** (`backend/app/services/runner.py`): `run_evaluation(...)` implements the
  data flow in `docs/architecture.md` exactly, including the timeout boundary
  (`ThreadPoolExecutor` + `future.result(timeout=...)`) and per-case / per-evaluator
  failure isolation.
- **CLI script** (`scripts/run_eval.py`): loads a dataset file, registers the agent/version/
  evaluators if missing, calls `run_evaluation`, prints a per-case and per-dimension
  summary.
- **Smoke dataset** (`datasets/stub-agent/smoke-v1/`, 7 cases): one per recognized root
  cause, one genuinely ambiguous case, and two deliberately-injected failure cases (an
  agent crash, and a wrong-but-non-crashing answer) used specifically to exercise failure
  isolation and prove a real regression gets caught rather than silently passed.
- **Tests** (`backend/tests/`): unit tests for the stub adapter and each deterministic
  evaluator; integration tests that run the full dataset through Postgres and assert (a)
  the run completes despite one case crashing, (b) the wrong-answer case is caught as a
  correctness failure rather than passing, and (c) a deliberately broken evaluator's
  failure doesn't affect any other evaluator's result for the same case. 12/12 passing.

## Deviations from the original plan

- **No JSON-schema-validation or numeric-tolerance evaluator yet** - only
  `structured_field_exact_match` was built. The roadmap's "exact match, JSON schema
  validation, numeric tolerance" was a menu of examples, not a checklist; one general
  field-equality evaluator was sufficient to prove the pattern for Phase 1's dataset. Add
  the others when a concrete case needs them (e.g. a numeric-tolerance case), rather than
  speculatively.
- **`completion_check` and `latency_threshold` were added beyond the plan's minimum.**
  The roadmap only required "deterministic evaluators only"; these two were added because
  they're free (derived straight from `CaseRunStatus`/`latency_ms`, no extra config) and
  they let the Phase 1 dataset exercise three methodology dimensions instead of one,
  making the per-dimension summary output meaningfully non-trivial.
- **Seed helpers instead of a seed script.** The plan's repository structure lists
  `scripts/seed_dev_data.py` as a later addition; Phase 1 needed the equivalent capability
  now (there's no CRUD API yet), so `backend/app/services/seed.py` provides
  `ensure_agent`/`ensure_agent_version`/`ensure_evaluator` get-or-create helpers, called
  directly by `scripts/run_eval.py`. A dedicated seed script can still be added later if a
  separate seeding step (independent of running an eval) becomes useful.
- **Dataset loading is its own module**, `backend/app/services/dataset_loader.py`
  (`load_dataset_from_file`), matching `scripts/load_dataset.py`'s intended job
  (ADR-0003) but implemented as an importable function rather than a standalone script,
  since Phase 1's CLI needed to call it directly. A thin `scripts/load_dataset.py` wrapper
  can be added when there's a reason to load a dataset independently of running it.
- **A real bug surfaced during implementation and is worth recording**: the runner
  initially read `dataset.cases` (the SQLAlchemy relationship) to get a run's cases. Newly
  loaded cases are attached by foreign key (`dataset_id=dataset.id`), not by appending to
  the relationship collection, so a dataset object whose `.cases` had already been
  accessed once earlier in the same session (as `load_dataset_from_file` does, to check
  for existing cases) held a stale, incomplete view. Fixed by having the runner query
  `EvaluationCase` directly by `dataset_id` instead of trusting the relationship cache.
  This is a general lesson for this codebase, not just a one-off fix: don't read an ORM
  relationship collection as a run's data source when the same session may have written to
  the underlying table by foreign key elsewhere first - query directly.

## Exit criteria verification

Roadmap Phase 1 exit criteria: *"`run_eval.py` runs a dataset against the stub adapter,
persists `CaseRun`/`ToolCall`/`EvaluationResult` rows, and prints a per-dimension summary
- with a deliberately broken agent version as a second test case, to confirm failure
isolation actually works."*

Verified by running `scripts/run_eval.py` against `datasets/stub-agent/smoke-v1/cases.yaml`:
the run completed with status `completed_with_errors` (the expected outcome given the two
injected-failure cases), all 7 cases produced `CaseRun` rows with `ToolCall` and
`EvaluationResult` children, the crashed case did not abort the run, and the wrong-answer
case was correctly scored as a `task_correctness` failure. The same guarantees are pinned
down as automated tests in `backend/tests/integration/test_runner.py` rather than only
having been checked by hand.

## What's still open going into Phase 2

- No FastAPI endpoints yet - everything is triggered via the CLI script, as planned.
- No rule-based evaluators yet (need `ToolCall` data to check tool selection/efficiency -
  the stub adapter already populates `tool_calls`, so this data is ready to evaluate
  against once Phase 2 builds those evaluators).
- The real Incident Investigation Platform adapter doesn't exist yet; Phase 1 deliberately
  used the stub adapter instead (per the roadmap's own reasoning: validate the platform
  without also depending on a second team's system).
