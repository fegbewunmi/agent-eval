# System Architecture

## Overview

```
                         ┌─────────────────────┐
                         │   Frontend (Next.js) │
                         │  browse / trigger /   │
                         │  inspect / compare    │
                         └──────────┬───────────┘
                                    │ HTTP (JSON)
                                    ▼
                         ┌─────────────────────┐
                         │   Backend API         │
                         │   (FastAPI)           │
                         │                       │
                         │  ┌─────────────────┐  │
                         │  │ Run Orchestrator │  │   <- "Evaluation Execution Layer"
                         │  └────────┬────────┘  │
                         │           │            │
                         │  ┌────────▼────────┐  │
                         │  │ Adapter Registry │──┼──► Agent Adapter ──► Target Agent
                         │  └─────────────────┘  │        (e.g. Incident Investigation
                         │  ┌─────────────────┐  │         Platform, out of process)
                         │  │ Evaluator        │  │
                         │  │ Registry         │  │
                         │  └─────────────────┘  │
                         └──────────┬───────────┘
                                    │ SQLAlchemy
                                    ▼
                         ┌─────────────────────┐
                         │   PostgreSQL          │
                         └─────────────────────┘
```

## Major components

### Backend API (FastAPI)

Owns all domain logic and is the only component that talks to Postgres. Responsibilities:

- CRUD endpoints for `Agent`, `AgentVersion`, `Dataset`, `EvaluationCase`, `Evaluator`.
- An endpoint to trigger an `EvaluationRun` (agent version + dataset + evaluator set).
- Endpoints to fetch run status, run summaries, and individual `CaseRun` detail (including
  trace and per-dimension results).
- A comparison endpoint: given two run IDs (or a run ID + "most recent prior run on this
  dataset"), compute and return a per-case, per-dimension diff.
- Minimal auth: a single static API key/bearer token is sufficient for MVP (see
  `product-overview.md` — no RBAC, no orgs).

The backend does **not** contain agent-specific logic. Anything specific to the Incident
Investigation Platform (or any other agent) lives in that agent's adapter, not in the API
or domain layer.

### Frontend (Next.js + TypeScript)

Visualization and workflow triggering only — it holds no business logic that the backend
doesn't also enforce; it is a client of the API.

- Browse agents, versions, datasets, and cases.
- Trigger a run (or view runs triggered via API/CLI) and watch its status.
- View a run summary: aggregate score per dimension, pass/fail counts, list of cases.
- Case inspector: input, expected behavior, actual output, full trace (tool calls,
  reasoning steps, timing), and every evaluator's score + reasoning for that case.
- Run comparison view: two runs side by side, per-case per-dimension deltas, regressions
  surfaced first.

The frontend is explicitly **not required for MVP** (see `roadmap.md`) — the API and a CLI
script are sufficient to prove the evaluation loop works. It is the deliverable of a later
phase.

### Database (PostgreSQL via SQLAlchemy)

Single relational store for all domain entities and results. Variable-shape data
(case inputs/expected values, raw adapter payloads, normalized traces, tool call
arguments/results, evaluator configs) is stored as JSONB columns with a documented,
Pydantic-validated schema at the application boundary — the database does not enforce
their internal shape, the application does. See `domain-model.md` for the full schema.

Runs and results are treated as an append-only, immutable log (ADR-0004): once an
`EvaluationRun` completes, its `CaseRun`s and `EvaluationResult`s are not mutated. Re-running
produces a new `EvaluationRun`. This is what makes version comparison trustworthy — you are
never comparing a run against a moving target.

### Evaluation execution layer ("the runner")

This is a logical layer, not necessarily a separate service. For MVP it is a Python module
invoked either synchronously from a FastAPI request handler (for small datasets) or from a
CLI script (`scripts/run_eval.py`) — both call the same `run_evaluation(...)` function so
there is exactly one code path for "run a dataset against a version."

Responsibilities:

1. Load the `Dataset`'s `EvaluationCase`s for the given `EvaluationRun`.
2. For each case, invoke the resolved `AgentAdapter.execute(case.input, version.config)`
   under a timeout, catching all exceptions at this boundary.
3. Persist the normalized result as a `CaseRun` (+ `ToolCall` rows).
4. For each configured `Evaluator`, invoke `evaluator.evaluate(case, execution_result)`,
   catching exceptions per (case, evaluator) pair, and persist `EvaluationResult` rows.
5. Update `EvaluationRun.status` as it progresses (`pending → running → completed` or
   `completed_with_errors`) so partial progress is visible even for long runs.

This layer is deliberately not a distributed job system. See ADR-0005.

### Agent adapter / integration layer

The seam that keeps the platform agent-agnostic. An `AgentAdapter` is a small Python
interface each integrated agent system implements once. The runner only ever talks to this
interface — never to LangGraph, or an HTTP client, or whatever the target agent happens to
use internally. Full detail in `agent-integration.md` and ADR-0001.

### Evaluators

Pluggable scorers registered by key, each declaring which dimension(s) it produces results
for. Four categories — deterministic, rule-based, LLM-as-judge, custom — detailed in
`evaluation-architecture.md` and ADR-0002/ADR-0007.

## Data flow (a single run)

1. Client (CLI or API caller) issues `POST /runs` with `agent_version_id`, `dataset_id`,
   and a list of `evaluator_id`s.
2. Backend creates an `EvaluationRun` row (`status=pending`), then invokes the runner
   (in-process for MVP).
3. Runner resolves the `AgentAdapter` for the `Agent` behind `agent_version_id`.
4. For each `EvaluationCase` in the dataset:
   a. Runner calls `adapter.execute(case.input, agent_version.config)`.
   b. Adapter invokes the target agent, captures timing, and returns a normalized
      `AgentExecutionResult` (see `agent-integration.md`) — or a result with
      `status=error` if the agent raised or timed out.
   c. Runner persists a `CaseRun` row and any `ToolCall` rows from the trace.
   d. Runner invokes each configured `Evaluator` against `(case, execution_result)` and
      persists `EvaluationResult` rows, isolating failures per evaluator.
5. Runner marks the `EvaluationRun` complete and computes aggregate per-dimension stats.
6. Client polls or fetches `GET /runs/{id}` for the summary, or `GET /runs/{id}/cases/{id}`
   for a single case's full detail, or `GET /runs/compare?a=...&b=...` for a diff.

## Failure boundaries

Failure isolation is a first-class design concern, not an afterthought, because the whole
point of the platform is to produce trustworthy signal even when the thing under test
misbehaves.

- **Adapter boundary.** The adapter must catch every exception raised by the target agent
  and normalize it into `AgentExecutionResult(status="error", error=...)`. The runner
  additionally wraps every `adapter.execute` call in its own try/except and timeout, in
  case an adapter fails to do this itself. A single case erroring never aborts the run —
  it is recorded and the run continues.
- **Evaluator boundary.** Each `(CaseRun, Evaluator)` pair is evaluated independently. If
  an LLM-as-judge evaluator's API call fails, that does not invalidate the deterministic
  or rule-based results for the same case — it is recorded as a missing/error
  `EvaluationResult` for that evaluator only.
- **Persistence boundary.** Database write failures are *not* swallowed — data integrity
  of what's already been recorded matters more than run availability. A failed write
  fails the run loudly rather than silently producing an incomplete, unflagged result set.
- **Timeout boundary.** `adapter.execute` is always wrapped in a runner-enforced timeout,
  independent of whatever timeout (if any) the adapter or target agent implements
  internally, so a hung agent cannot hang an entire evaluation run.
- **Trust boundary.** The adapter is the only code in the system that understands a given
  agent's internals. Nothing on the platform side (runner, evaluators, API, frontend)
  should ever need to know that the Incident Investigation Platform uses LangGraph, or how
  any other integrated agent is built.
