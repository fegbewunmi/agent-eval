# Product Overview

## Problem being solved

Teams building AI agents change them constantly: prompts, tool definitions, orchestration
graphs, models, retrieval sources. Every change is a bet that behavior improved. Today that
bet is usually validated by:

- a developer eyeballing a handful of transcripts,
- an informal Slack thread of "looks better to me",
- or nothing at all until a user complains.

None of this scales, none of it is repeatable, and none of it catches regressions in the
long tail of scenarios that don't happen to be in the developer's head that day.

The Agent Evaluation Platform exists to answer, with evidence instead of vibes:

> **When I change an AI agent, did it actually get better?**

It does this by treating agent evaluation like a test suite with graded, inspectable
results instead of a pass/fail CI gate — because "better" is multi-dimensional (correct,
grounded, safe, efficient, fast, cheap) and collapsing it into one number hides regressions.

## Intended users

- **Agent developers** (primary) — e.g. the team building the Incident Investigation
  Platform — who want to know, before shipping, whether a prompt/tool/model change is a
  net improvement or a regression.
- **Eval/quality engineers** who curate datasets, tune evaluators, and maintain the
  correctness of the evaluation process itself.
- **Reviewers / tech leads** who need to inspect *why* a case failed, not just that it did,
  before approving a change.

Not initially targeted: end users of the agents being evaluated, non-technical
stakeholders, or external customers of a hosted eval product. This is an internal
engineering tool first.

## Primary workflows

1. **Register an agent and its versions.** A developer registers an `Agent` (e.g.
   "incident-investigator") once, and registers each meaningfully distinct build as an
   `AgentVersion` (e.g. a git SHA, a prompt revision, a model swap).
2. **Define an evaluation dataset.** A developer (or eval engineer) authors `EvaluationCase`
   records: an input scenario plus the expected behavior — an expected output, an expected
   tool-call pattern, or a qualitative rubric — grouped into a `Dataset`.
3. **Run an agent version against a dataset.** The developer triggers an `EvaluationRun`:
   the platform invokes the agent (via its adapter) once per case, capturing output,
   structured data, and a normalized execution trace as a `CaseRun`.
4. **Evaluate outputs and traces across multiple dimensions.** Configured `Evaluator`s
   (deterministic, rule-based, LLM-as-judge, or custom) score each `CaseRun` on one or more
   independent dimensions, producing `EvaluationResult` rows. No dimension is silently
   averaged into a single "AI score" (see `evaluation-methodology.md`).
5. **Inspect individual failures.** For any case, the developer can see the input, the
   expected behavior, the actual output, the full normalized trace (including tool calls,
   arguments, and results), and every evaluator's score and reasoning for that case.
6. **Compare results between versions to detect regressions.** Given two `EvaluationRun`s
   over the same dataset (e.g. v1 vs v2), the platform produces a per-case, per-dimension
   diff: what got better, what got worse, and what's unchanged — surfaced as regressions,
   not just moved averages.

## MVP scope

The MVP must prove the full loop end-to-end on one real adapter, without needing a UI or
LLM-as-judge to do it:

- CRUD (via API, not necessarily UI) for `Agent`, `AgentVersion`, `Dataset`,
  `EvaluationCase`, `Evaluator`.
- One working adapter for the Incident Investigation Platform.
- A run orchestration path: given an `AgentVersion` + `Dataset` + a set of `Evaluator`s,
  execute every case, persist `CaseRun`, `ToolCall`, and `EvaluationResult` rows.
- **Deterministic and rule-based evaluators only.** LLM-as-judge is valuable but adds
  nondeterminism and cost that would obscure whether the *platform* is working correctly.
  It is deferred to a later phase (see `roadmap.md`).
- A way to inspect a run's results and a single case's failure in detail (API responses are
  acceptable for MVP; a minimal UI is a stretch goal, not a requirement).
- A way to compare two runs over the same dataset and see per-case, per-dimension deltas.
- Postgres persistence with a schema that will not need to be redesigned when LLM-as-judge,
  additional adapters, or a UI are added later.
- Synchronous, in-process execution (see ADR-0005) — no task queue, no worker fleet.

## Explicitly out of scope (for now)

- Multi-tenant organizations, billing, or usage metering.
- Complex RBAC — at most, a single shared credential/API key for internal use.
- Kubernetes, service meshes, or any distributed systems infrastructure.
- Distributed task queues (Celery, Ray, etc.) — see ADR-0005 for why this is deferred
  rather than ruled out forever.
- Auto-generating evaluation datasets with an LLM (an obvious future feature; not MVP,
  and mixing it in early would make it hard to trust the datasets used to validate the
  platform itself).
- Automatic agent improvement or prompt-optimization loops. This platform measures agents;
  it does not change them.
- Real-time evaluation while an agent is executing (streaming judgment). Evaluation is a
  post-hoc step over a completed execution trace.
- Full production observability: dashboards, alerting, SLOs. This is an evaluation tool,
  not an APM.
- Statistical significance testing / formal experiment framework (e.g. confidence
  intervals on pass rates, sequential testing). Worth having eventually; premature before
  there's usage data to know what's needed. Tracked in `open-questions.md`.
- Human annotation queues/workflows for building "gold" labels. The data model does not
  preclude this later, but no UI or workflow for it exists in MVP.
- Out-of-the-box support for arbitrary agent frameworks. The platform supports any agent
  through the adapter interface (`agent-integration.md`), but it does not ship adapters,
  orchestration helpers, or framework-specific tooling for frameworks it hasn't been asked
  to integrate.
