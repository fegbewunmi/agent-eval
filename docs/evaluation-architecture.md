# Evaluation Architecture

## Common interface

Every evaluator, regardless of category, implements the same contract:

```python
class Evaluator(ABC):
    key: str
    dimension: str  # e.g. "correctness", "tool_efficiency", "safety"

    def evaluate(
        self,
        case: EvaluationCase,
        execution_result: AgentExecutionResult,
    ) -> list[EvaluationResult]:
        ...
```

An evaluator usually produces one `EvaluationResult` (one dimension), but the interface
allows returning several if a single pass naturally produces more than one (e.g. an
LLM-judge prompt that scores both correctness and grounding in one call) — with the
understanding that doing so makes each sub-score harder to reason about independently, so
it should be the exception, not the default.

The runner treats every evaluator identically: it does not know or care whether an
evaluator is deterministic, rule-based, LLM-based, or custom. Category only matters for
*choosing which evaluators to configure*, not for how the runner invokes them.

## Categories

### Deterministic evaluators

Pure functions over `execution_result` and `case.expected` with no judgment involved:
exact string match, regex match, JSON-schema validation of `structured_output`, numeric
equality within a tolerance, set equality of extracted fields.

**Use for:** cases with a single objectively correct answer or a structured output
contract — "did the agent extract the correct incident ID," "is `structured_output` valid
against schema X," "is the reported host name exactly right."

**Do not use for:** anything where multiple phrasings/approaches are legitimately correct,
or subjective quality dimensions (helpfulness, clarity, tone). Forcing these into exact
matches produces false negatives that erode trust in the whole eval suite.

**Properties:** fully deterministic, free, instant, no external dependency. This is why
they are the only evaluator category in Phase 1 of the roadmap — they let the platform's
own correctness be validated without evaluator noise as a confound.

### Rule-based evaluators

Heuristics over the *structured trace* (tool calls, ordering, counts) rather than the
free-text output: "must call `fetch_logs` before `propose_root_cause`," "must not call
`page_oncall` more than once," "must not invoke a mutating tool for a read-only scenario,"
"must complete within N tool calls."

**Use for:** process/procedure correctness, safety constraints expressible as explicit
rules, tool selection, and tool efficiency — anything that can be checked against the
structured `tool_calls` list or trace shape without needing to understand free-text
semantics.

**Do not use for:** judging the semantic quality or correctness of free-text content, or
anything that would require an ever-growing pile of brittle special cases to approximate
judgment a human would apply instantly. If a rule needs more than a handful of clauses to
express, that is a signal the dimension actually needs an LLM-as-judge.

**Properties:** deterministic given a fixed trace, fast, free, but only as good as the
rules — silent under-coverage (a real failure mode the rules don't check for) is the main
risk, so rule-based evaluator coverage should be reviewed periodically, not "set and
forget."

### LLM-as-judge evaluators

A rubric-driven prompt that asks an LLM to score the agent's free-text output (and
optionally the trace) against `case.expected`, which may itself be qualitative
("the root-cause explanation should correctly identify disk exhaustion as the primary
cause and reference the specific host from the logs").

**Use for:** correctness of natural-language explanations where valid phrasings vary,
grounding/faithfulness (does the final narrative's claims trace back to evidence actually
present in the trace, rather than being fabricated), and any dimension where "expected" is
inherently a description of good behavior rather than an exact value.

**Do not use for:** anything a deterministic or rule-based evaluator can already answer
more cheaply and reliably — never reach for an LLM judge to check an exact-match-able
fact. Also avoid using LLM-as-judge as the *sole* signal for a regression-gating decision;
it is inherently noisier than the other categories.

**Mitigations for noise (required, not optional, once this category is enabled):**
- Pin an exact judge model version and use temperature 0 (or as close to deterministic as
  the provider allows) so that re-running the *same* case run through the *same* evaluator
  version gives a stable score.
- Always store `reasoning` alongside `score` so a human can audit *why* the judge scored
  something the way it did — an unexplained LLM score is close to useless for debugging.
- Version the evaluator (`Evaluator.version`) whenever the rubric prompt or judge model
  changes, so historical results remain attributable to the exact judge that produced them
  (ADR-0008).
- Periodically calibrate judge scores against a small set of human-labeled cases to check
  the judge hasn't drifted or has systematic bias, rather than trusting it blindly.

**Properties:** costs money and time per case, non-deterministic in the general case
(mitigated above but never eliminated), and requires a working LLM API — this is why it is
explicitly deferred past Phase 1 of the roadmap (ADR-0007).

### Custom developer-defined evaluators

An escape hatch: any Python callable conforming to the `Evaluator` interface, registered
with `type="custom"`. For domain-specific logic that doesn't fit cleanly into the other
three buckets — e.g. embedding-based semantic similarity, a replay/simulation check, a
metric specific to one integrated agent.

**Use for:** anything genuinely project-specific that the platform's built-in categories
don't cover well. This category exists so the platform doesn't need to anticipate every
possible evaluation need up front.

**Do not use for:** logic that actually is deterministic, rule-based, or LLM-as-judge —
classify it correctly so it's discoverable and so the mitigations above (e.g. judge
calibration) still apply where relevant. "Custom" should be a genuine last resort, not a
place where everything ends up out of convenience.

**Properties:** whatever the developer builds — the platform provides no special
guarantees for this category beyond the interface contract. Not implemented in MVP
(Phase 1–2); the interface is designed to allow it later without a schema change (evaluator
`type` already includes `custom`).

## No blended score

Regardless of category, evaluators never get averaged into one number. See
`evaluation-methodology.md` for why, and for how per-dimension results are aggregated and
compared across runs.
