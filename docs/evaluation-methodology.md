# Evaluation Methodology

## Why not one "AI score"

A single blended score is the fastest way to make a regression invisible: if tool
efficiency gets worse but correctness gets better, an average can stay flat or even
improve while the agent has genuinely gotten worse along a dimension someone cares about.
Different stakeholders care about different dimensions (a safety regression matters even
if correctness is unchanged; a latency regression matters even if the answer is right).
The platform therefore always reports **per-dimension** results, and a "regression" is
defined per case, per dimension - never as a change in a combined number.

This is a direct consequence of the evaluator architecture (`evaluation-architecture.md`):
each `Evaluator` reports on exactly one `dimension`, and `EvaluationResult` rows are never
averaged together into a stored "overall score." Aggregation, where it happens at all, is
a display-time computation (e.g. "pass rate for dimension X across the run") and is always
shown broken out by dimension, never collapsed further.

## Dimensions

| Dimension | What it measures | Typical evaluator category |
|---|---|---|
| **Task correctness** | Did the agent produce the right answer / conclusion for the scenario? | Deterministic (when an exact/structured answer exists) or LLM-as-judge (when correctness requires judging free text against a qualitative expectation) |
| **Grounding** | Are the claims in the final output actually supported by evidence present in the trace (e.g. the logs the agent retrieved), rather than fabricated? | LLM-as-judge, comparing `final_output` against evidence extracted from `trace` |
| **Tool selection** | Did the agent choose the right tools for the scenario (right tools, not necessarily in a specific order)? | Rule-based, over `ToolCall` records |
| **Tool efficiency** | Did the agent use tools economically - no redundant calls, no excessive back-and-forth - relative to what the scenario requires? | Rule-based (call counts, redundancy checks) |
| **Safety** | Did the agent avoid disallowed or dangerous actions (e.g. a mutating action in a read-only scenario, paging someone who shouldn't be paged)? | Rule-based for hard constraints; LLM-as-judge for nuanced content-safety judgments |
| **Completion** | Did the agent actually finish the task (vs. erroring, timing out, or stopping partway)? | Deterministic, from `CaseRun.status` directly |
| **Latency** | How long did the case take end-to-end? | Deterministic, from `CaseRun.latency_ms` |
| **Cost** | What did the case cost (tokens/dollars), where knowable? | Deterministic, from `CaseRun.token_usage` / `cost_usd`, when the adapter reports them |

This list is a starting set, not exhaustive or fixed - new dimensions are added by
registering a new `Evaluator` with a new `dimension` value; no schema change is needed
(`EvaluationResult.case_run_id` / `evaluator_id` already generalizes to any dimension).

## How dimensions combine into a report

A run's summary is a **matrix**, not a scalar: rows are dimensions, columns are aggregate
stats (pass rate, mean score, count of cases evaluated, count of evaluator errors). A
run's summary view should let this matrix be sliced by `EvaluationCase.tags` (e.g. "pass
rate for `tool_efficiency` restricted to `high-severity` cases") because an aggregate over
the whole dataset can hide a regression concentrated in one scenario category.

**`EvaluationResult.passed = None` means "not applicable to this case," not "failed," and
must be excluded from every mean/pass-rate computation, not just displayed differently.**
An evaluator reports `passed=None` when the case simply didn't configure the expected
value that evaluator checks (e.g. `structured_field_minimum` on a case with no
`structured_output_minimums`) - this is expected for datasets where not every case
exercises every configured evaluator, and folding those into the average as if they were
0-scoring failures silently deflates the dimension's mean score. This was caught in
practice (docs/phase-notes/phase-2.md) when adding evaluators whose expected config isn't
present on every case dragged `task_correctness`'s mean down for reasons that had nothing
to do with the agent's actual performance.

## Regression detection between two runs

Given `EvaluationRun A` (baseline) and `EvaluationRun B` (candidate) over the *same*
dataset:

1. For every `EvaluationCase` present in both runs, and every dimension evaluated in both,
   compute the delta between A's and B's `EvaluationResult.score` (or `passed`).
2. Classify each (case, dimension) pair as **regressed** (meaningfully worse in B),
   **improved** (meaningfully better in B), or **unchanged**.
3. **Regressions are surfaced first and explicitly**, listed by case - not folded into an
   aggregate delta. A version that improves the mean score of a dimension while regressing
   three specific cases has *not* unambiguously gotten better, and the report must not
   imply that it has.
4. Aggregate deltas (e.g. "correctness pass rate: 82% → 88%") are shown as summary context
   *alongside* the case-level regression list, never as a replacement for it.
5. If `dataset_snapshot_hash` (see `domain-model.md`, ADR-0003) differs between the two
   runs, the comparison is flagged as potentially confounded by dataset drift rather than
   silently presented as a clean agent-only comparison.

## Statistical caution

- Datasets are expected to be small, hand-curated collections, not large statistically
  powered samples - a pass-rate change of a few percentage points on a 30-case dataset is
  often just one or two cases flipping, not a statistically meaningful trend. The platform
  reports raw counts/case lists alongside any percentage precisely so this isn't
  obscured.
- LLM-as-judge scores are noisier than deterministic/rule-based ones by construction (see
  `evaluation-architecture.md`). Do not treat a one-off LLM-judge score delta on a single
  case as proof of a regression without checking the `reasoning` field; do treat a
  consistent pattern across several related cases as meaningful signal.
- Formal statistical significance testing (confidence intervals, sequential testing) is
  out of scope for now - see `product-overview.md` and `open-questions.md`. It's a
  reasonable future addition once there's real usage data showing it's needed, not before.
