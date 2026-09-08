# 0007. Deterministic evaluation vs. LLM-as-judge sequencing

Status: Accepted

## Context

LLM-as-judge is the most flexible evaluator category - it can approximate a human's
judgment of open-ended output - and it's tempting to reach for it immediately since many
interesting evaluation questions ("is this root-cause explanation actually correct and
well-grounded") are qualitative. But LLM-as-judge is also the platform's most complex and
least trustworthy-by-default building block: it costs money per case, is inherently
somewhat nondeterministic even at temperature 0, depends on an external API being
available, and its own correctness (is the judge actually judging well?) is itself an
unsolved measurement problem the first time it's introduced.

If the platform's *own* correctness (does the runner correctly execute cases, isolate
failures, and persist results?) is validated at the same time LLM-as-judge is introduced,
any bug is ambiguous: is the runner wrong, or is the judge just noisy? That ambiguity is
expensive to debug.

## Decision

Sequence evaluator categories so deterministic and rule-based evaluators are built and
validated first (Phase 1–2 of `docs/roadmap.md`), with LLM-as-judge deliberately deferred
to Phase 3, after the runner, adapter, and comparison logic have already been proven
correct against noise-free evaluators. When LLM-as-judge is introduced, it comes with the
mandatory mitigations listed in `docs/evaluation-architecture.md` (pinned model/temperature,
stored reasoning, evaluator versioning per ADR-0008, periodic human calibration) - it is
not treated as a drop-in fourth evaluator with no additional process around it.

## Alternatives considered

- **Build LLM-as-judge from the start, since it's the most valuable/flexible category.**
  Rejected for the sequencing reason above: it would make Phase 1 (proving the platform
  itself works) much harder to validate cleanly, and risks the team debugging "is my
  runner broken" and "is my judge broken" simultaneously.
- **Skip deterministic/rule-based evaluators for the real target agent and rely on
  LLM-as-judge for everything**, since the Incident Investigation Platform's output is
  largely qualitative. Rejected: per `docs/evaluation-architecture.md`, several MVP-critical
  dimensions (completion, tool selection under explicit constraints, latency, cost) are
  cleanly checkable deterministically/by rule and should never depend on a judge call.

## Consequences

- Phase 1 can be validated on its own terms - a wrong or missing deterministic result is
  either a runner bug or an adapter bug, never "maybe the judge was just noisy" -
  because no LLM-as-judge evaluator exists yet at that point.
- Some real evaluation needs for the Incident Investigation Platform (e.g. grounding of
  its root-cause narrative) simply cannot be fully assessed until Phase 3. This is an
  accepted, explicit gap during Phases 1–2, not a silent omission - reviewers of interim
  results should read run summaries knowing grounding isn't yet measured.
- The mitigations required alongside LLM-as-judge (ADR-0008's versioning, calibration)
  are themselves nontrivial process work, correctly scheduled for when the category is
  actually introduced rather than designed speculatively now.
