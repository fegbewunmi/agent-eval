# Domain Model

This document defines the entities, then evaluates the originally proposed model and
recommends changes. The recommendations are reflected in the schema below; rationale for
each deviation follows.

## Entity-relationship summary

```
Agent 1───N AgentVersion
Dataset 1───N EvaluationCase
AgentVersion 1───N EvaluationRun ◄───N Dataset
EvaluationRun 1───N CaseRun ◄───N EvaluationCase   (one CaseRun per case, per run)
CaseRun 1───N ToolCall
CaseRun 1───N EvaluationResult ◄───N Evaluator
```

## Entities

### Agent

The logical system under test (e.g. "incident-investigator"). Stable across versions.

| field | type | notes |
|---|---|---|
| id | UUID | |
| name | text | unique |
| description | text | |
| adapter_key | text | selects the `AgentAdapter` implementation (see ADR-0001) |
| created_at | timestamptz | |

### AgentVersion

A specific, pinned, immutable build of an `Agent` — a git SHA, a prompt revision, a model
swap. Immutable once created: if you need to change config, register a new version.

| field | type | notes |
|---|---|---|
| id | UUID | |
| agent_id | FK → Agent | |
| version_label | text | e.g. `"v1.2.0"` or a git SHA; unique per agent |
| config | JSONB | adapter-specific: endpoint URL, git ref, model params, etc. |
| description | text | changelog / what changed vs. the prior version |
| created_at | timestamptz | |

### Dataset

A named collection of `EvaluationCase`s.

| field | type | notes |
|---|---|---|
| id | UUID | |
| name | text | unique |
| description | text | |
| created_at | timestamptz | |

**Open question:** whether `Dataset` itself needs versioning (a dataset's cases can be
edited after runs have used it, which threatens reproducibility of historical runs). MVP
answer and rationale are in ADR-0003; tracked further in `open-questions.md`.

### EvaluationCase

One scenario: an input to give the agent, and the expected behavior to check for.

| field | type | notes |
|---|---|---|
| id | UUID | |
| dataset_id | FK → Dataset | |
| key | text | stable human-readable id within the dataset, e.g. `"disk-full-single-host"` |
| input | JSONB | whatever the target agent's adapter needs as input |
| expected | JSONB | expected output / expected tool-call pattern / rubric notes — shape is evaluator-dependent, not enforced by the DB |
| tags | text[] | e.g. `["multi-tool", "high-severity"]`, used for segmented reporting |
| metadata | JSONB | free-form (source, author, notes) |
| created_at / updated_at | timestamptz | |

### EvaluationRun

One execution of one `AgentVersion` against one `Dataset` with one set of `Evaluator`s.
Immutable once `status = completed` (ADR-0004).

| field | type | notes |
|---|---|---|
| id | UUID | |
| agent_version_id | FK → AgentVersion | |
| dataset_id | FK → Dataset | |
| evaluator_ids | UUID[] or join table | evaluator set used, frozen at run start |
| dataset_snapshot_hash | text | hash of case content at run start, for drift detection (ADR-0003) |
| status | enum | `pending`, `running`, `completed`, `completed_with_errors`, `failed` |
| started_at / completed_at | timestamptz | |
| triggered_by | text | free-form: user, CI job, script |
| notes | text | optional free-form annotation |

### CaseRun

The persisted, normalized result of running one `EvaluationCase` through the agent, within
one `EvaluationRun`. This is where the adapter's `AgentExecutionResult` (see
`agent-integration.md`) lands.

| field | type | notes |
|---|---|---|
| id | UUID | |
| evaluation_run_id | FK → EvaluationRun | |
| evaluation_case_id | FK → EvaluationCase | |
| status | enum | `success`, `error`, `timeout` |
| final_output | text | primary human-readable output |
| structured_output | JSONB \| null | if the agent produces structured data |
| normalized_trace | JSONB | ordered list of trace steps, common envelope (see `agent-integration.md`) |
| raw_output | JSONB | adapter's unprocessed response, kept for debugging/re-normalization |
| latency_ms | numeric | |
| token_usage | JSONB \| null | `{prompt_tokens, completion_tokens, total_tokens}` |
| cost_usd | numeric \| null | |
| error | JSONB \| null | `{type, message}` when status != success |
| created_at | timestamptz | |

### ToolCall

Extracted from the trace into its own table because tool-selection and tool-efficiency
evaluators need to query/count/order tool calls without parsing JSON trace blobs.

| field | type | notes |
|---|---|---|
| id | UUID | |
| case_run_id | FK → CaseRun | |
| sequence_index | int | order within the case run |
| tool_name | text | |
| arguments | JSONB | |
| result | JSONB | |
| status | enum | `success`, `error` |
| latency_ms | numeric | |
| started_at | timestamptz | |

### Evaluator

A registered, versioned scorer. Versioned like `AgentVersion` — see "Recommended changes"
below for why.

| field | type | notes |
|---|---|---|
| id | UUID | |
| key | text | stable family identifier, e.g. `"exact_match"`, `"root_cause_grounding_judge"` |
| version | text | bumped whenever config/prompt/logic changes meaningfully |
| type | enum | `deterministic`, `rule_based`, `llm_judge`, `custom` |
| dimension | text | the dimension this evaluator reports on, e.g. `"correctness"`, `"tool_efficiency"` |
| config | JSONB | thresholds, rubric prompt, judge model, etc. |
| description | text | |
| created_at | timestamptz | |

### EvaluationResult

One evaluator's judgment of one `CaseRun`, on one dimension.

| field | type | notes |
|---|---|---|
| id | UUID | |
| case_run_id | FK → CaseRun | |
| evaluator_id | FK → Evaluator | |
| score | numeric | normalized `0.0–1.0` |
| passed | boolean \| null | optional binary threshold view of `score`, where applicable |
| reasoning | text \| null | especially for LLM-as-judge; explains the score |
| raw_output | JSONB | evaluator's unprocessed output |
| created_at | timestamptz | |

## Evaluating the originally proposed model — recommended changes

The prompt's candidate list was: `Agent, AgentVersion, Dataset, EvaluationCase,
EvaluationRun, CaseRun, Evaluator, EvaluationResult, Trace, ToolCall`. Recommendations:

1. **Drop `Trace` as a separate table; keep it as a schema/concept, not a row.**
   A `Trace` would be 1:1 with `CaseRun` — there is no relational benefit to splitting it
   into its own table, only an extra join. `CaseRun.raw_output` and
   `CaseRun.normalized_trace` (both JSONB) carry what a `Trace` table would have held.
   "Trace" remains an important *domain concept* — it has its own normalized Pydantic
   schema, described in `agent-integration.md` — it just isn't its own SQL table. If a
   future need arises for independent trace querying beyond tool calls (e.g. querying
   reasoning steps at scale), promote it then; don't build it speculatively now.

2. **Keep `ToolCall` as its own table, but only because two MVP evaluation dimensions
   (tool selection, tool efficiency) need to query it relationally** — count calls, check
   ordering, check for forbidden/missing tools. This is the one piece of the trace worth
   the extra table; everything else stays inside `normalized_trace` JSONB.

3. **Add explicit versioning to `Evaluator`.** The original list treats `Evaluator` as if
   it were stable, but evaluator logic changes over time just like agent logic does
   (a rubric prompt gets tuned, a rule gets stricter). If `EvaluationResult` rows don't
   record *which version* of an evaluator produced them, a run-to-run comparison can be
   comparing an agent change confounded with an evaluator change — which defeats the whole
   purpose of the platform. `Evaluator.version` plus `EvaluationRun.evaluator_ids` freezing
   the exact evaluator rows used addresses this. See ADR-0008.

4. **`EvaluationRun` needs an explicit dimension/evaluator-set snapshot**, not just a
   dataset and agent version. Without this, "what was actually measured" for a historical
   run is undiscoverable once evaluator configs change later.

5. **No separate `Comparison` entity for MVP.** A comparison between two runs is a
   read-only computation over already-immutable data (ADR-0004), not something that needs
   its own stored row. If users later want to save/name/annotate a comparison for sharing,
   add a lightweight `Comparison` (two run IDs + a name) then — don't build persistence for
   it before there's a demonstrated need.

6. **`Dataset` mutability is a real open question, not a settled one.** Cases will get
   fixed, added, and retired over time. Making `Dataset` fully immutable (like
   `AgentVersion`) forces awkward "dataset v2" duplication for every typo fix. Making it
   freely mutable risks silently invalidating the meaning of historical runs. MVP decision
   (ADR-0003): cases are mutable, but every `EvaluationRun` stores a `dataset_snapshot_hash`
   so drift is at least *detectable* when comparing runs, even though full point-in-time
   dataset snapshots are not implemented in MVP. Revisit if drift turns out to bite often.

7. **`EvaluationCase.tags`** was not in the original list but is added because the
   methodology (see `evaluation-methodology.md`) depends on segmented reporting (e.g.
   "how does this version do specifically on high-severity, multi-tool cases?"), and tags
   are the simplest mechanism for that.

8. **No per-`ToolCall` `EvaluationResult`.** Evaluators operate at the `CaseRun` level and
   can inspect the full `tool_calls` list to make a judgment (e.g. "was the *set and order*
   of tool calls correct"). A separate evaluation result per individual tool call was
   considered and rejected as unnecessary granularity for MVP — it multiplies result rows
   without a clear consumer. Revisit only if a concrete evaluation need requires per-call
   scoring.

The result is a model with the same conceptual coverage as the proposed one, but with
`Trace` folded into `CaseRun`, `Evaluator` explicitly versioned, and two deliberately
deferred concerns (dataset versioning, per-tool-call scoring) documented rather than
silently resolved.
