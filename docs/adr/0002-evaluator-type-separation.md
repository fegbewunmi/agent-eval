# 0002. Evaluator type separation

Status: Accepted

## Context

Agent quality checks range from exact-match assertions to open-ended LLM judgments of
free text. It would be simplest to implement one `Evaluator` interface and let every
evaluator do whatever it wants internally. But conflating categories invites two specific
failures observed in similar systems: deterministic checks quietly reimplemented as LLM
calls (slow, costly, non-reproducible for something that didn't need judgment at all), and
genuinely subjective checks forced into brittle rule sets that silently under-cover real
failure modes.

## Decision

Formally categorize every `Evaluator` as `deterministic`, `rule_based`, `llm_judge`, or
`custom` (stored as `Evaluator.type`), with documented guidance on what each is and is not
for (`docs/evaluation-architecture.md`). All four share one interface and are invoked
identically by the runner - the category is a classification and selection aid for
developers, not a different code path in the runner.

## Alternatives considered

- **A single undifferentiated `Evaluator` type with no category.** Simpler schema, but
  loses the ability to reason about a run's evaluator mix (e.g. "how much of this run's
  signal depends on a nondeterministic LLM call?") and provides no forcing function to push
  developers toward the cheapest adequate evaluator category for a given check.
- **Separate interfaces per category** (e.g. `DeterministicEvaluator`,
  `LlmJudgeEvaluator` as unrelated classes). Rejected because the runner would then need
  per-category invocation logic, which contradicts the goal (`docs/architecture.md`) of the
  runner treating all evaluators uniformly; a single interface with a `type` field achieves
  the same classification benefit without duplicating the invocation path.

## Consequences

- Phase 1 of the roadmap can be scoped precisely to "deterministic evaluators only,"
  which is only meaningful because the category is explicit and enforced in the schema.
- Reviewers can ask "should this be rule-based instead of LLM-as-judge?" as a concrete
  question during evaluator design, per the guidance in `evaluation-architecture.md`.
- The category is self-reported by whoever registers the evaluator; nothing currently
  prevents a developer from mislabeling a check (e.g. registering something LLM-based as
  `custom` to avoid the LLM-judge mitigations). This is accepted as a review-process
  concern, not a technical one, for now.
