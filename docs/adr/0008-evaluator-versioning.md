# 0008. Evaluator versioning

Status: Accepted

## Context

The originally proposed domain model (see the design brief and `docs/domain-model.md`)
treats `Evaluator` as a stable reference entity, similar to how one might first think of a
lookup table. In practice, evaluator logic changes over time just as agent logic does: a
rule-based check gets stricter, an LLM-judge rubric prompt gets refined, a deterministic
tolerance gets tightened. If `EvaluationResult` rows don't record exactly which version of
an evaluator produced them, then a run-to-run comparison intended to isolate an *agent*
change can be silently confounded by an *evaluator* change that happened in between -
directly undermining the platform's core purpose (ADR-0004's immutability guarantee is
necessary but not sufficient without this).

## Decision

`Evaluator` carries an explicit `version` field alongside a stable `key` (the family
identifier, e.g. `"root_cause_grounding_judge"`). Any meaningful change to an evaluator's
config, rubric prompt, judge model, or logic is treated as a new `Evaluator` row (same
`key`, new `version`), not an in-place edit of the existing row - mirroring how
`AgentVersion` treats agent changes. `EvaluationRun` freezes the exact set of `Evaluator`
rows (by ID, which encodes both `key` and `version`) used at run time. The comparison logic
in `docs/evaluation-methodology.md` checks whether the same evaluator *version* was used on
both sides of a comparison for each dimension and flags it when not, the same way it flags
dataset drift (ADR-0003).

## Alternatives considered

- **Treat `Evaluator` as immutable-and-fixed, with no versioning need** (the originally
  implicit assumption). Rejected once it became clear evaluator tuning is a normal,
  expected activity - an unversioned model would make that activity silently corrosive to
  comparison trustworthiness.
- **A separate `EvaluatorVersion` child entity**, mirroring `Agent`/`AgentVersion` exactly.
  Considered and functionally similar; rejected in favor of a single `Evaluator` table with
  a `version` field for MVP because evaluators are not expected to accumulate as many
  versions as agents will, and a single table is simpler. Revisit if evaluator version
  history management (e.g. listing all versions of a given evaluator key) becomes a common
  need with its own UI/API surface.

## Consequences

- Evaluator authors must remember to bump `version` on meaningful change - this is
  currently a discipline/process requirement, not a technical enforcement (see the related
  open question in `docs/open-questions.md` about auto-hashing evaluator config to make
  this automatic).
- Historical `EvaluationResult` rows remain interpretable indefinitely: given a result, its
  `evaluator_id` always resolves to the exact config/prompt/logic that produced it, even
  after that evaluator has since been revised.
- This is a direct, explicit deviation from the originally proposed domain model, made and
  justified in `docs/domain-model.md` point 3.
