# Phase 2 notes - real adapter, rule-based evaluators, API

Status: complete. What was built against the plan in `docs/roadmap.md`, where it
deviated, a real bug the live integration surfaced, and how the exit criteria were
verified - against the actual target system running for real, not a mock of it.

## What was built

- **The real adapter** (`backend/app/adapters/incident_investigator/adapter.py`) for
  [ai-operations-center](https://github.com/fegbewunmi/ai-operations-center), a LangGraph
  multi-agent incident investigator running on FastAPI + Gemini 2.5 Flash (Vertex AI) +
  Cloud SQL. It starts an investigation (`POST /v1/investigations` or
  `/v1/investigations/replay/{fixture_id}`), polls `GET .../status` until a terminal phase,
  then normalizes `findings`/`timeline`/`evidence`/`analysis` into
  `AgentExecutionResult` - trace steps from the timeline (mapped by event source: planner →
  reasoning, the three specialist agents → tool_call, synthesizer → message, the action
  dispatcher → handoff), `ToolCallRecord`s from the specialist findings, and token
  usage/cost summed from the target system's own per-node accounting. This file is the
  only place in the codebase that knows the target agent uses LangGraph, Vertex AI, or
  Cloud SQL, per ADR-0001.
- **Two rule-based evaluators** (`backend/app/evaluators/rule_based/`):
  `required_tool_calls` (tool_selection - did the agent call every specialist the scenario
  needs) and `no_redundant_tool_calls` (tool_efficiency - did it call any specialist more
  than once), both operating purely on `AgentExecutionResult.tool_calls`.
- **One new deterministic evaluator**, `structured_field_minimum`
  (`backend/app/evaluators/deterministic/`): a numeric floor check (e.g. confidence must
  be ≥ 75%), general enough to reuse for any numeric structured-output field, not just
  confidence.
- **FastAPI endpoints** (`backend/app/api/runs.py`, wired in `backend/app/main.py`):
  `POST /runs`, `GET /runs/{id}`, `GET /runs/{id}/cases/{case_run_id}`, and
  `GET /runs/compare` - all wrapping the same `run_evaluation`/`compare_runs` service
  functions the CLI already used, per the "one code path" rule in `docs/architecture.md`.
- **The comparison service** (`backend/app/services/comparison.py`): per-dimension mean
  scores, case-level regressions/improvements classified by `passed` transitions, dataset
  drift detection (`dataset_snapshot_hash` mismatch, ADR-0003), and evaluator-version
  mismatch detection (ADR-0008) - the comparison is flagged as potentially confounded when
  either side changed under the run being compared.
- **A real dataset** (`datasets/incident-investigator/smoke-v1/`, 3 cases) built from the
  target system's *own* committed eval fixtures
  (`backend/eval/fixtures/{INC-FD-001,INC-LR-001,INC-RL-001}.json` in that repo) via its
  `/replay/{fixture_id}` endpoint - deterministic evidence, real LLM reasoning. `expected`
  values are copied from each fixture's own `ground_truth` block rather than invented
  independently.
- **28 automated tests** (12 unit for the adapter against a mocked HTTP transport shaped
  like the real API, 6 for the new evaluators, 5 API integration tests via FastAPI's
  `TestClient` against the stub adapter, plus the 23 carried over from Phase 1 - some
  extended). All pass. None of them make live GCP/LLM calls - that's deliberate (cost,
  determinism, CI speed); the adapter's correctness against the *real* system was verified
  separately, live, below.

## Verified against the real system, not a mock

This phase didn't stop at "the adapter should work" - the actual
[ai-operations-center](https://github.com/fegbewunmi/ai-operations-center) backend was
started locally (against its real `ai-ops-db` Cloud SQL instance and real Vertex AI
Gemini calls), and the Phase 2 dataset was run against it for real, twice:

1. **First run failed** - every case errored with `404 Not Found` on the very first
   status poll. This was real signal, not a test artifact: see "a real bug" below.
2. **Second run, after the fix, passed cleanly**: all 3 cases (`INC-FD-001`, `INC-LR-001`,
   `INC-RL-001`) completed successfully, correctly identified the ground-truth root cause
   and affected service, cleared their confidence floors (95%/85%/89%-ish against 85%/75%/
   75% minimums), called every required specialist, and called none of them twice.
   `completion`, `latency`, `task_correctness`, `tool_selection`, and `tool_efficiency` all
   scored a clean 1.00 mean. Each investigation took roughly 60–75 seconds end to end,
   consistent with the target system's own README claim ("under 2 minutes").

This is the strongest evidence so far that the adapter/evaluator/runner design actually
holds up against a real, independently-built multi-agent system, not just the stub.

## A real bug the live run found

The target system's `POST /v1/investigations(/replay/...)` returns `202` immediately and
starts the LangGraph investigation via `asyncio.create_task` - there is no guarantee the
background task's first checkpoint write has landed by the time that response reaches the
caller. The adapter's very first `GET .../status` call, issued right after receiving the
`202`, raced that write and got back `404 Investigation not found`, which
`response.raise_for_status()` turned into an exception, which the adapter correctly (per
its own contract) turned into `AgentExecutionResult(status="error")` - but incorrectly as
a *judgment*: the investigation wasn't broken, it just hadn't started yet.

Fixed by treating a `404` during polling the same as a non-terminal phase (keep polling
until `max_wait_seconds`) rather than as a terminal failure - see
`_poll_until_terminal` in the adapter. Added
`test_execute_survives_404_race_right_after_starting` to pin this down. This is a good
illustration of why `docs/agent-integration.md`'s adapter responsibilities are entirely
this file's problem to get right: a background-task-based agent API is a very different
shape than a synchronous one, and the platform's core (runner, evaluators) needed zero
changes to accommodate it.

## A real methodology bug the expanded evaluator set found

Running the Phase 1 stub dataset again with the new `structured_field_minimum` and
`required_tool_calls` evaluators added (neither configured on that dataset's cases,
since it predates them) revealed that `task_correctness`'s mean score dropped from 0.71 to
0.36 for no reason related to the agent's actual behavior - every `passed=None`
("not applicable to this case") result was being averaged in as if it scored 0. Fixed in
both `scripts/run_eval.py`'s summary and `app/services/comparison.py`'s
`dimension_stats_for_run`, and written down as a permanent rule in
`docs/evaluation-methodology.md` ("How dimensions combine into a report") rather than a
one-off fix, since any future aggregation code must follow it too.

## Deviations from the original plan

- **No `safety`-dimension rule-based evaluator yet.** The roadmap's "tool selection, tool
  efficiency, safety-constraint rules" was a menu; the real fixtures used so far don't
  define a safety constraint to check (no case where a specific tool must *not* be
  called), so one wasn't built speculatively. Add it against a concrete case when one
  exists.
- **`GET /runs/compare` lives in `runs.py`, not a separate `comparisons.py`** as
  `docs/repository-structure.md`'s illustrative tree suggested - comparison is a
  three-line route wrapping one service call; a whole extra router file for it would be
  the kind of premature structure the design brief asks to avoid. Split it out if the
  comparison surface grows (e.g. a saved/named comparison entity, per the open question in
  `docs/domain-model.md` point 5).
- **No CRUD endpoints for `Agent`/`Dataset`/`Evaluator` yet** - this matches the roadmap's
  actual Phase 2 scope ("wrap the runner," not "build full CRUD"), so registration still
  goes through `app/services/seed.py`, called from `scripts/run_eval.py`. Still an open
  gap for anyone who wants to manage agents/datasets without touching the CLI or a DB
  client directly; not scheduled until something concretely needs it.
- **A route-ordering subtlety worth remembering**: `GET /runs/compare` had to be
  registered *before* `GET /runs/{run_id}` in `app/api/runs.py`, or Starlette would match
  `/runs/compare` against the `{run_id}` pattern first and fail UUID parsing on the
  literal string `"compare"`. Any future literal path under `/runs/` needs the same care.

## What's still open going into Phase 3

- LLM-as-judge evaluators (grounding, in particular - this system's `supporting_evidence`
  list is exactly the kind of thing a grounding judge should check against the underlying
  telemetry/deployment/knowledge findings).
- Evaluator versioning is implemented in the schema and exercised in comparison logic, but
  nothing has bumped a version yet - genuinely untested against a real version change
  until Phase 3 tunes an LLM-judge rubric.
- No frontend; the API is capable enough now that Phase 4 doesn't need new backend work
  to build one, per the roadmap's intent.
