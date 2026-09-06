# 0004. Immutable evaluation runs and results

Status: Accepted

## Context

The platform's core value proposition is trustworthy version comparison: "did this agent
version actually get better?" That claim is only defensible if the two things being
compared — two `EvaluationRun`s — are stable, inspectable records of what actually
happened, not values that could have been edited after the fact. If runs or results could
be mutated post-completion (e.g. "fix up" a `CaseRun` after noticing an error, or edit an
`EvaluationResult` score directly), a comparison could no longer be trusted to reflect two
real, reproducible executions.

## Decision

Once an `EvaluationRun` reaches a terminal status (`completed`, `completed_with_errors`,
`failed`), it and every `CaseRun`, `ToolCall`, and `EvaluationResult` row under it are
treated as append-only and immutable. There is no "edit a run" or "edit a result"
operation. If something about the run's inputs was wrong (a bad dataset case, a
misconfigured evaluator), the fix is: correct the underlying `EvaluationCase` or
`Evaluator`, and create a **new** `EvaluationRun`. Old runs remain as an honest historical
record, even if later found to be based on a flawed dataset case — the dataset fix is
visible as a new, separate run rather than rewriting history.

## Alternatives considered

- **Allow in-place correction of run/result data** (e.g. an admin UI to fix a wrong
  score). Rejected: any comparison that includes a run with silently-edited results is no
  longer trustworthy evidence of what the agent actually did at that point in time, which
  undermines the entire product goal.
- **Soft-delete/archive runs instead of true immutability.** Considered, but immutability
  is about not-editing, not about hiding — archival is an orthogonal, lower-priority
  concern (not addressed in MVP; a run can simply be excluded from a query if it's no
  longer relevant).

## Consequences

- Re-running a dataset always produces a new `EvaluationRun`, even for identical inputs —
  this is a feature, not waste: it lets non-determinism in the agent or in LLM-as-judge
  evaluators be observed directly by comparing two runs that were supposed to be identical.
- The comparison feature (`docs/evaluation-methodology.md`) can rely on both sides of a
  diff being stable — no defensive re-checking of "did this run change under me" is needed
  beyond the dataset-drift check from ADR-0003.
- Storage grows monotonically (every run is kept forever in MVP). Not a concern at
  expected MVP scale (tens to low hundreds of runs); a retention/archival policy is a
  reasonable future addition once volume actually warrants it, not now.
