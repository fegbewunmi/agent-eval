# Phase 3 notes - LLM-as-judge, evaluator versioning, dataset tooling

Status: complete. What was built against the plan in `docs/roadmap.md`, a real grounding
failure the judge caught live (not a contrived test case), and how the exit criteria were
verified.

## What was built

- **The `llm_judge` category, for real**: `GeminiJudgeClient`
  (`backend/app/evaluators/llm_judge/client.py`) calls Vertex AI's Gemini
  `generateContent` REST endpoint directly via `httpx`, authenticated through `gcloud`'s
  Application Default Credentials rather than adding a Google SDK dependency - see
  ADR-0009 for the tradeoff and its real limitation (requires the `gcloud` CLI wherever
  this runs).
- **`grounding_judge`** (`backend/app/evaluators/llm_judge/grounding.py`, dimension
  `grounding`): checks whether the claims an agent lists as `supporting_evidence` are
  actually backed by the tool call results it gathered, or fabricated/extrapolated.
  Needs no case-specific `expected` configuration - it checks the agent's own claims
  against its own gathered evidence, so it applies to any adapter whose
  `structured_output` includes a `supporting_evidence: list[str]`, not just the incident
  investigator's.
- **The required LLM-as-judge mitigations from `docs/evaluation-architecture.md`**,
  actually enforced rather than just documented: temperature pinned to `0.0` by default
  (verified by test), `reasoning` always stored on the `EvaluationResult`, and the
  evaluator versioned like everything else (ADR-0008) - a rubric or model change is a new
  `Evaluator` row (new `version`), not an edit of the existing one.
- **A real interface gap closed**: `Evaluator` previously had no way to access its own DB
  `config` - deterministic/rule-based evaluators had gotten away with using
  `case.expected` for everything, but a judge's model/project/temperature are properties
  of the *evaluator*, not the case. `Evaluator.__init__(self, config=None)` was added to
  the base class and threaded through `get_evaluator()`/the runner. No existing evaluator
  needed to change.
- **Evaluator versioning, exercised end-to-end**: `test_evaluator_versioning.py` registers
  `grounding_judge` as both `v1` and `v2`, runs the same dataset through each, and confirms
  `compare_runs` flags the mismatch - proving out the promise ADR-0008 made back in Phase 2
  rather than leaving it as an untested code path.
- **Dataset tooling**: `scripts/load_dataset.py` (load without running - previously this
  capability only existed embedded inside `run_eval.py`), a `?tag=` filter on
  `GET /runs/{id}` that restricts both the case list and the per-dimension stats to cases
  carrying that tag (the segmented-reporting capability `evaluation-methodology.md` always
  called for but nothing had built yet), and `docs/dataset-authoring.md` - a concrete guide
  to `expected` shapes per evaluator, tags, and the process for adding cases or whole new
  datasets.
- **9 new tests** (5 for the grounding judge against a fake client, 1 for evaluator
  versioning, 2 for a dataset-loader bug fixed this phase, 1 for tag filtering) - 37 total,
  all passing, none making live calls.

## Verified live, twice

1. **The judge itself, against real Phase 2 data.** Pulled an actual `CaseRun` from
   Phase 2's live run (INC-FD-001, the real Gemini-produced `supporting_evidence` and tool
   call results already sitting in the dev database) and ran `GroundingJudge` against it
   for real: correctly passed all 6 genuine claims. Then injected an obviously fabricated
   claim ("the payments database was physically relocated to a new data center in
   Antarctica the night before the incident") into the same data and re-ran it - the judge
   correctly flagged exactly that claim as ungrounded and left everything else passing.
   This is real discriminative evidence the judge does its job, not just that it returns
   valid JSON.

2. **The full CLI path, live, with the judge attached.** Ran
   `scripts/run_eval.py --judge-project-id ai-ops-center-eb26` against the real
   incident-investigator dataset (all 3 fixtures) through the real AI Operations Center
   backend. `INC-FD-001` and `INC-LR-001` passed grounding cleanly. `INC-RL-001` did not:

   > "The evidence provided does not contain an initial 'Incident description' with the
   > specific details about '23% of stock reservation requests failing' or 'payload size
   > issues'... it's not part of an initial incident report in the evidence."

   The agent's `supporting_evidence` had restated details from the original incident
   *description* (given to it, not gathered by a tool call) as if they were evidence it
   found. That's a real, substantive nuance - not a fabrication in the "invented facts"
   sense, but a legitimate question about what should count as "evidence I gathered" vs.
   "information I was handed" - exactly the kind of judgment call a rule-based evaluator
   cannot make and an LLM judge can, with a stored explanation a human can read and agree
   or disagree with. Whether restating the given incident description like this is a
   dataset-worthy or a metric issue depends on a call the target system's owners need to
   make; the platform's job here was surfacing it clearly and non-destructively, which it
   did.

Sanity-checked first against the free stub-agent dataset (`--judge-project-id` attached
but the stub agent has no `supporting_evidence` field) to confirm the wiring doesn't crash
before spending real API calls - `grounding` correctly reported "not applicable" for all 7
cases there.

## Deviations from the original plan

- **Only one LLM-judge evaluator was built (`grounding_judge`), not several.** The
  roadmap's "LLM-as-judge evaluators" was scoped down deliberately to the one dimension
  Phase 2's notes specifically flagged as the obvious first candidate. A qualitative
  correctness judge is a natural second one - not built now because the current datasets'
  `expected` values are all precise categorical fields that deterministic evaluators
  already check well; build it against a dataset that actually needs qualitative
  correctness judgment, not speculatively.
- **No calibration tooling.** `docs/evaluation-architecture.md` requires periodic
  calibration against human labels as an LLM-judge mitigation; this is correctly a
  process, not code, and `docs/roadmap.md` already scheduled calibration tooling for
  Phase 5 with real usage data informing what it needs to look like. Not built here.
- **The `gcloud` CLI credential dependency (ADR-0009) is a real, tracked limitation**, not
  silently accepted - see `docs/open-questions.md` item 9. Fine for this project's current
  local-development reality; would need `google-auth` before any real deployment.
  *(Confirmed exactly as predicted once a real deployment happened - see
  `docs/phase-notes/deployment.md`, written after this phase and describing current
  system state, not the local-only reality described here.)*

## What's still open going into Phase 4

- A qualitative correctness judge (see above) if a dataset that needs one shows up.
- No frontend yet; the API surface (now including tag-filtered run summaries) shouldn't
  need backend changes to support one, consistent with the roadmap's intent for Phase 4.
- The INC-RL-001 grounding finding above is a legitimate open question for whoever owns
  the target system's `supporting_evidence` semantics - not something this platform should
  resolve unilaterally by tweaking the rubric until it stops flagging it.
