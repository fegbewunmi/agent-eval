# 0003. Evaluation dataset representation

Status: Accepted

## Context

Datasets need to be (a) easy for developers/eval engineers to author and review — ideally
in a normal code-review flow — and (b) queryable and joinable against runs/results in
Postgres. They also raise a reproducibility question: if a case is edited after a run has
used it, does the historical run's meaning silently change?

## Decision

- **Authoring format:** dataset cases are authored as files (YAML or JSON, one file or
  small set of files per dataset) under `datasets/<agent>/<dataset-name>/`, reviewed via
  normal pull requests, and loaded into the database via `scripts/load_dataset.py`. The
  database is the runtime source of truth once loaded; the files are the human-editable
  source of truth for authoring and review.
- **Storage shape:** `EvaluationCase.input` and `.expected` are stored as JSONB with no
  DB-enforced internal schema — validity is enforced by the adapter (for `input`, since
  only the adapter knows what shape its target agent needs) and by each evaluator (for
  `expected`, since only the evaluator knows what shape it needs to check). This mirrors
  the adapter/evaluator boundary already established in ADR-0001/0002.
- **Mutability:** `Dataset`/`EvaluationCase` rows are mutable (cases can be fixed, added,
  retired). Full immutability (like `AgentVersion`) was considered but rejected as too
  rigid — it would force a new dataset version for every typo fix. Instead, every
  `EvaluationRun` stores `dataset_snapshot_hash` (a hash over the case content actually
  used), so that comparing two runs can detect — and flag — dataset drift between them,
  even though the platform does not keep full point-in-time snapshots of dataset content.

## Alternatives considered

- **Author datasets directly through a UI/API, no file-based authoring.** Rejected for
  MVP: it would require the frontend (Phase 4) to exist before any dataset could be
  created at all, and it loses the code-review workflow that file-based authoring gets for
  free.
- **Fully immutable, versioned datasets** (`DatasetVersion` mirroring `AgentVersion`).
  Considered more rigorous — guarantees exact reproducibility — but adds real friction
  (every case fix requires a new dataset version) for a benefit (guaranteed point-in-time
  reproducibility) that isn't yet known to be needed. Recorded as an open question in
  `docs/open-questions.md` rather than ruled out permanently; revisit if drift-related
  confusion actually occurs in practice.
- **Enforce a fixed schema for `input`/`expected` via the database (e.g. separate typed
  columns).** Rejected because the shape genuinely varies per adapter/evaluator and a fixed
  schema would need to be a superset of every agent's needs — exactly the kind of
  premature generalization the design brief asks to avoid.

## Consequences

- Dataset changes go through normal code review, which is valuable given that a bad
  dataset (wrong expected behavior) produces misleading evaluation signal just as easily
  as a bad evaluator does.
- Comparisons across runs must check `dataset_snapshot_hash` and surface a warning on
  mismatch (implemented per `docs/evaluation-methodology.md`); consumers of the comparison
  API must not ignore this flag.
- If reproducibility requirements turn out to be stricter than "detect drift after the
  fact," this decision will need revisiting — tracked explicitly in `open-questions.md`
  rather than left implicit.
