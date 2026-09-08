# Implementation Roadmap

Phases are ordered so that the platform's own correctness can be validated before adding
sources of nondeterminism (LLM-as-judge) or surface area (a UI, more adapters). Each phase
should be shippable and useful on its own.

**All planned phases (0-5) are complete.** Phase 5 was explicitly scoped as the closing
phase - see `phase-notes/phase-5.md`. No Phase 6 is planned; further work (a third
adapter, revisiting synchronous execution, custom evaluators, calibration tooling) is
listed under Phase 5 below as explicitly deferred until real evidence justifies it, not
scheduled.

## Phase 0 - Design (this deliverable)

Architecture, domain model, ADRs, evaluation methodology, roadmap. No application code.
Exit criteria: this document set is coherent and the major decisions in `docs/adr/` are
recorded (even where marked "open" in `open-questions.md`).

## Phase 1 - Deterministic core loop, no UI, no LLM judge

**Status: complete.** See `phase-notes/phase-1.md` for what was built, how it deviated
from this plan, and how the exit criteria were verified.

The smallest slice that proves the whole loop end-to-end:

- Postgres schema + Alembic migrations for the full domain model in `domain-model.md`
  (`Agent`, `AgentVersion`, `Dataset`, `EvaluationCase`, `EvaluationRun`, `CaseRun`,
  `ToolCall`, `Evaluator`, `EvaluationResult`) - build the real schema now even though only
  part of it is exercised this phase, so later phases don't require a migration rewrite.
- The `AgentAdapter` and `Evaluator` base interfaces (`app/adapters/base.py`,
  `app/evaluators/base.py`) and their registries.
- One adapter: can be a minimal/stub adapter (e.g. a deterministic fake agent) rather than
  the real Incident Investigation Platform, specifically so Phase 1 can validate the
  runner and schema without also depending on a second team's system being ready.
- Deterministic evaluators only (exact match, JSON-schema validation, numeric tolerance).
- The runner (`app/services/runner.py`) with full failure isolation as described in
  `architecture.md`, invokable from a CLI script (`scripts/run_eval.py`) - no API required
  yet.
- A small hand-authored dataset (5–15 cases) under `datasets/` to run against.
- Exit criteria: `python scripts/run_eval.py --agent-version ... --dataset ...` runs a
  dataset against the stub adapter, persists `CaseRun`/`ToolCall`/`EvaluationResult` rows,
  and prints a per-dimension summary - with a deliberately broken agent version as a second
  test case, to confirm failure isolation actually works (a case that errors doesn't kill
  the run, an evaluator that errors doesn't kill the case).

## Phase 2 - Real adapter + rule-based evaluators + API

**Status: complete.** See `phase-notes/phase-2.md` for what was built, a real bug the live
integration surfaced, and how the exit criteria were verified against the actual target
system (not a mock of it).

- Build the real `IncidentInvestigatorAdapter`, including the LangGraph-trace-to-
  `normalized_trace` mapping described in `agent-integration.md`.
- Add rule-based evaluators (tool selection, tool efficiency, safety-constraint rules)
  operating on `ToolCall` records.
- Wrap the runner in FastAPI endpoints (`POST /runs`, `GET /runs/{id}`,
  `GET /runs/{id}/cases/{id}`) - still synchronous execution (ADR-0005).
- Add the comparison endpoint (`GET /runs/compare`) implementing the regression-detection
  logic in `evaluation-methodology.md`.
- Exit criteria: a developer can trigger a real run of the Incident Investigation Platform
  against a dataset via the API and get back a per-case, per-dimension result set; two runs
  over the same dataset can be diffed and regressions are visible.

## Phase 3 - LLM-as-judge + evaluator versioning + dataset tooling

**Status: complete.** See `phase-notes/phase-3.md` - includes a real grounding failure the
judge caught live, an edge case worth a human's attention rather than a clean pass/fail.

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

## Phase 4 - Frontend

**Status: complete.** See `phase-notes/phase-4.md` - one real gap surfaced and closed
(read-only catalog endpoints the browsing UI needed but the API didn't have yet, plus a
real display bug caught only by actually looking at a screenshot).

- Next.js app: agent/version/dataset browsing, run triggering + status, the case
  inspector (trace viewer, tool-call timeline, per-dimension results with reasoning), and
  the run comparison view (regressions surfaced first, per `evaluation-methodology.md`).
- No new backend capability should be required here beyond what Phases 1–3 already expose
  through the API - if the frontend needs a new endpoint shape, that's a signal something
  was missing from the API design, not a reason to add frontend-only logic.

## Phase 5 - Prove agent-agnosticism, revisit execution model

**Status: complete.** See `phase-notes/phase-5.md` - the headline result: the abstraction
generalized to a second, structurally different real agent (a RAG app, Document Q&A)
completely unchanged. No `AgentAdapter`/`AgentExecutionResult`/runner/persistence/
comparison/frontend changes were needed; only a new adapter file and two new
general-purpose deterministic evaluators, justified by a concrete gap (substring
containment over free text) rather than added speculatively. No ADR needed to change as a
result. This is the platform's last planned phase - see "Explicit non-goals" below.

- Integrated one second adapter for a structurally different agent (Document Q&A, a RAG
  app) to validate that `AgentExecutionResult` and the adapter interface generalize, per
  `agent-integration.md`. No core-code change was needed to onboard it - confirming the
  Phase 1–2 contract was complete rather than incidentally incident-investigator-shaped. A
  third adapter (e.g. a SQL agent) was judged unnecessary once the second one confirmed
  the pattern; add one later only if a genuinely different agent shape shows up.
- ADR-0005 (synchronous execution) was deliberately left unchanged - this phase produced
  no evidence synchronous execution is inadequate (Document Q&A's real queries took
  2-3 seconds each), consistent with the "only revisit with real evidence" instruction.
- Custom evaluator support was not added - the one concrete gap this phase found
  (substring containment in free text) was still cleanly expressible as new
  `deterministic` evaluators, not a case requiring the `custom` category.
- LLM-judge calibration tooling and the statistical-caution items in
  `evaluation-methodology.md` remain not-yet-needed; no usage volume has emerged that
  would justify them.

## Explicit non-goals across all phases

See `product-overview.md` "Explicitly out of scope" - billing/orgs/RBAC, Kubernetes,
distributed task queues (until Phase 5 revisits it with evidence), LLM-generated datasets,
automatic agent improvement, real-time streaming evaluation, and formal statistical
significance testing are not scheduled in any phase above. If a future need makes one of
these necessary, it should get its own ADR at that time rather than being folded in
silently.
