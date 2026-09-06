# Implementation Roadmap

Phases are ordered so that the platform's own correctness can be validated before adding
sources of nondeterminism (LLM-as-judge) or surface area (a UI, more adapters). Each phase
should be shippable and useful on its own.

## Phase 0 — Design (this deliverable)

Architecture, domain model, ADRs, evaluation methodology, roadmap. No application code.
Exit criteria: this document set is coherent and the major decisions in `docs/adr/` are
recorded (even where marked "open" in `open-questions.md`).

## Phase 1 — Deterministic core loop, no UI, no LLM judge

**Status: complete.** See `phase-notes/phase-1.md` for what was built, how it deviated
from this plan, and how the exit criteria were verified.

The smallest slice that proves the whole loop end-to-end:

- Postgres schema + Alembic migrations for the full domain model in `domain-model.md`
  (`Agent`, `AgentVersion`, `Dataset`, `EvaluationCase`, `EvaluationRun`, `CaseRun`,
  `ToolCall`, `Evaluator`, `EvaluationResult`) — build the real schema now even though only
  part of it is exercised this phase, so later phases don't require a migration rewrite.
- The `AgentAdapter` and `Evaluator` base interfaces (`app/adapters/base.py`,
  `app/evaluators/base.py`) and their registries.
- One adapter: can be a minimal/stub adapter (e.g. a deterministic fake agent) rather than
  the real Incident Investigation Platform, specifically so Phase 1 can validate the
  runner and schema without also depending on a second team's system being ready.
- Deterministic evaluators only (exact match, JSON-schema validation, numeric tolerance).
- The runner (`app/services/runner.py`) with full failure isolation as described in
  `architecture.md`, invokable from a CLI script (`scripts/run_eval.py`) — no API required
  yet.
- A small hand-authored dataset (5–15 cases) under `datasets/` to run against.
- Exit criteria: `python scripts/run_eval.py --agent-version ... --dataset ...` runs a
  dataset against the stub adapter, persists `CaseRun`/`ToolCall`/`EvaluationResult` rows,
  and prints a per-dimension summary — with a deliberately broken agent version as a second
  test case, to confirm failure isolation actually works (a case that errors doesn't kill
  the run, an evaluator that errors doesn't kill the case).

## Phase 2 — Real adapter + rule-based evaluators + API

- Build the real `IncidentInvestigatorAdapter`, including the LangGraph-trace-to-
  `normalized_trace` mapping described in `agent-integration.md`.
- Add rule-based evaluators (tool selection, tool efficiency, safety-constraint rules)
  operating on `ToolCall` records.
- Wrap the runner in FastAPI endpoints (`POST /runs`, `GET /runs/{id}`,
  `GET /runs/{id}/cases/{id}`) — still synchronous execution (ADR-0005).
- Add the comparison endpoint (`GET /runs/compare`) implementing the regression-detection
  logic in `evaluation-methodology.md`.
- Exit criteria: a developer can trigger a real run of the Incident Investigation Platform
  against a dataset via the API and get back a per-case, per-dimension result set; two runs
  over the same dataset can be diffed and regressions are visible.

## Phase 3 — LLM-as-judge + evaluator versioning + dataset tooling

- Add the `llm_judge` evaluator category with the mitigations required in
  `evaluation-architecture.md` (pinned model/temperature, stored reasoning, calibration
  process).
- Implement `Evaluator.version` handling end-to-end (ADR-0008) and confirm comparisons
  correctly flag when evaluator versions differ between two runs, analogous to the
  dataset-drift flag in Phase 2.
- Dataset authoring/import tooling (`scripts/load_dataset.py`), tagging support, and a
  documented process for adding new cases.
- Exit criteria: correctness and grounding can be judged for cases with qualitative
  expected behavior, with reasoning stored and inspectable per case.

## Phase 4 — Frontend

- Next.js app: agent/version/dataset browsing, run triggering + status, the case
  inspector (trace viewer, tool-call timeline, per-dimension results with reasoning), and
  the run comparison view (regressions surfaced first, per `evaluation-methodology.md`).
- No new backend capability should be required here beyond what Phases 1–3 already expose
  through the API — if the frontend needs a new endpoint shape, that's a signal something
  was missing from the API design, not a reason to add frontend-only logic.

## Phase 5 — Prove agent-agnosticism, revisit execution model

- Integrate a second and third adapter for structurally different agents (e.g. a RAG app
  and a SQL agent) specifically to validate that `AgentExecutionResult` and the adapter
  interface generalize, per `agent-integration.md`. Any change needed to core code (rather
  than just a new adapter file) to onboard these is a signal the Phase 1–2 contract was
  incomplete.
- Revisit ADR-0005 (synchronous execution) if run volume or dataset size by this point
  actually justifies background/async execution — only then, with real evidence, not
  speculatively.
- Add custom evaluator support if a concrete need has emerged that deterministic/
  rule-based/LLM-judge don't cover.
- Consider LLM-judge calibration tooling, and revisit the statistical-caution items in
  `evaluation-methodology.md` if usage has revealed a real need for them.

## Explicit non-goals across all phases

See `product-overview.md` "Explicitly out of scope" — billing/orgs/RBAC, Kubernetes,
distributed task queues (until Phase 5 revisits it with evidence), LLM-generated datasets,
automatic agent improvement, real-time streaming evaluation, and formal statistical
significance testing are not scheduled in any phase above. If a future need makes one of
these necessary, it should get its own ADR at that time rather than being folded in
silently.
