# Phase 4 notes - frontend

Status: complete. What was built against the plan in `docs/roadmap.md`, a real backend
gap the frontend surfaced (exactly the situation the roadmap anticipated), a real display
bug caught only by looking at a rendered screenshot, and how the exit criteria were
verified.

## What was built

- **A Next.js App Router frontend** (`frontend/`) with zero client components. Every page
  is a Server Component that fetches from the backend directly; the two mutating flows
  (trigger a run, pick two runs to compare) use native HTML forms - a Server Action for
  the run trigger (`app/runs/new/actions.ts`), a plain GET form for the comparison picker
  (query params double as the page's state). No state-management library, no client-side
  fetch library, no CSS framework - one global stylesheet. This is the concrete instance
  of the deferred styling/state decision in `docs/tech-stack.md`: nothing in this UI
  needed client-side state, so nothing was added.
- **Pages**: a dashboard (recent runs), agent/version browsing, dataset browsing with a
  case-list detail view, a run-trigger form, a run summary page (per-dimension stats, tag
  filter chips, case list), a full case inspector (input/expected, output, evaluation
  results, tool calls, trace - all matching the CLI's output structure from Phases 1-3),
  and a run comparison page (regressions surfaced before aggregate stats, with dataset-drift
  and evaluator-version-mismatch warnings from `compare_runs`).
- **A real backend gap, found and closed exactly the way the roadmap anticipated.** The
  plan explicitly said: *"if the frontend needs a new endpoint shape, that's a signal
  something was missing from the API design, not a reason to add frontend-only logic."*
  There was no way to *list* agents, datasets, evaluators, or runs - only fetch one by ID.
  Closed with four new read-only endpoints (`backend/app/api/catalog.py`: `GET /agents`,
  `GET /datasets`, `GET /datasets/{id}`, `GET /evaluators`) and one addition to the
  existing runs router (`GET /runs`, list with optional `dataset_id`/`agent_version_id`
  filters). Deliberately **read-only** - no create/update/delete - since dataset creation
  already has its own established path (file authoring + `scripts/load_dataset.py`,
  ADR-0003) and adding a UI form for it would work against that decision, not extend it.
- **CORS**, added to `backend/app/main.py` for defensive/debugging convenience (a
  permissive `localhost:*` allowlist, appropriate for an internal tool with no auth), even
  though the frontend's own request path doesn't need it - every actual data fetch happens
  server-to-server between Next.js and FastAPI, never from the browser.
- **6 new backend tests** (catalog endpoints + run listing), 43 total, all passing.

## Verified live - and a real bug only a screenshot caught

Following the "start the dev server and use the feature in a browser before reporting
complete" rule: no `chromium-cli` was available in this environment, so a small
Playwright driver was installed and used instead (per the `run` skill's documented
fallback) to load every page against the *real* backend - including the actual Phase 2/3
live-run data already sitting in the dev database - and capture screenshots.

Every page returned `200` with zero console errors on the first pass. That would have
been reported as "done." Looking at the actual screenshots instead of trusting the status
codes caught a real bug: evaluator versions were rendering as `vv1` instead of `v1` in
three places (the run-trigger form's evaluator checkboxes, the case inspector's evaluation
results table, and the comparison page's version-mismatch warning) - a `v{version}`
template literal prepending an extra `v` onto a version string that already contains one
(`"v1"`, not `"1"`). Fixed in all three places, then re-screenshotted to confirm.

The case inspector was also verified against the real, substantive Phase 3 finding: the
`INC-RL-001` grounding failure (the agent restating the incident description as gathered
evidence, see `docs/phase-notes/phase-3.md`) renders correctly end to end - full reasoning
text, the real cost (`$0.0037`), the real trace with all 11 steps including the terminal
`handoff` to the action dispatcher, and all three tool calls with expandable arguments/
results.

## Deviations from the original plan

- **`docs/repository-structure.md`'s illustrative API tree** (`agents.py`, `datasets.py`,
  `runs.py`, `comparisons.py`, one file per resource) wasn't followed literally - the
  actual read-only catalog surface is small enough that one `catalog.py` covers
  agents/datasets/evaluators, and comparison stayed inside `runs.py` (a decision already
  made and justified in `docs/phase-notes/phase-2.md`). Updated the illustrative tree to
  match reality rather than forcing reality to match a tree written before any of this
  existed.
- **No loading states, optimistic UI, or client-side validation.** `POST /runs` still runs
  synchronously (ADR-0005) and can take several minutes for the real adapter - the
  run-trigger page says so in plain text and lets the browser's native full-page form
  submission handle the wait, rather than building a polling/progress UI for a problem
  ADR-0005 already accepted for the API layer. Revisit together if ADR-0005 itself is ever
  revisited (Phase 5).
- **No auth, no per-user anything** - matches `docs/product-overview.md`'s MVP scope
  (single shared internal tool, no orgs/RBAC). The CORS policy reflects this too.

## What's still open going into Phase 5

- Proving agent-agnosticism with a second/third structurally different adapter is
  unaffected by anything built here - the frontend reads the same generic API shapes
  (`AgentExecutionResult`-derived `CaseRunDetail`, etc.) regardless of which adapter
  produced them, so a new adapter needs no frontend changes, only new data flowing through
  already-built pages.
- Revisiting ADR-0005's synchronous execution model, if real usage volume justifies it, is
  still the one thing that would meaningfully change the run-trigger page's UX (from "wait
  for the page to load" to "watch a status poll").
