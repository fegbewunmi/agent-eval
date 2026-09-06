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

## A serious post-launch bug, found through real usage of the frontend

After Phase 4 shipped, actually using the "trigger a new run" form against the real
incident-investigator (not the stub agent) surfaced a genuine correctness bug in the
runner's timeout boundary - the same boundary `docs/architecture.md` documents as a core
failure-isolation guarantee going back to Phase 1.

**Symptom:** triggering a run against the real adapter with the form's default 30s
per-case timeout took ~3 minutes total for 3 cases and reported every single case as
`status=timeout` - even though 30s x 3 should have failed fast, not slow.

**Root cause:** `_execute_with_timeout` (`app/services/runner.py`) used
`with ThreadPoolExecutor(...) as pool:`. That context manager calls
`pool.shutdown(wait=True)` on `__exit__` *regardless of which branch returns* - including
the `except FutureTimeoutError` branch. So even though `future.result(timeout=30)`
correctly raised at 30 seconds, the function did not actually return to its caller until
the background thread's real ~60-75s call finished anyway - at which point the function
threw away the real result and returned a stale "timeout" instead. The configured timeout
provided zero benefit (the wall-clock wait was unbounded by it) and pure downside (the
real result was computed and then discarded). This directly contradicted the "timeout
boundary" guarantee documented since Phase 1 - it existed in the code from Phase 1 onward
and was never previously exercised against a call slow enough to expose it, since the
stub agent responds in under a millisecond.

**Fix:** dropped the `with` statement; call `pool.shutdown(wait=False)` explicitly in
every branch instead, so the function returns as soon as it has an answer (or gives up)
rather than waiting on the context manager's implicit blocking shutdown. Python cannot
forcibly cancel a running thread, so an abandoned call's thread keeps running to
completion in the background with its result discarded - an accepted, documented
consequence (see the updated docstring), not a further bug to chase: it means a process
hosting the runner won't exit cleanly until abandoned threads finish, and a real
LLM-backed adapter still gets billed for a call whose result is thrown away.

**Verified three ways:** an isolated reproduction of the bug pattern (a bare
`ThreadPoolExecutor` + `time.sleep`, confirming the old pattern makes a caller wait ~2s for
a 0.2s-configured timeout); a new regression test
(`tests/unit/test_runner_timeout.py`) proving the fixed function returns promptly instead
of waiting on a slow fake adapter; and a live call against the real adapter with a 5s
timeout, confirming a `status=timeout` result now returns in ~5s instead of ~60-90s.

**Also fixed as part of the same investigation:** the run-trigger form's default timeout
(30s) was a real footgun against the real adapter even *with* the bug fixed - 30s is far
below the ~60-90s a real investigation needs. Raised the default to 200s (comfortably
above the adapter's own internal `max_wait_seconds`) and added an inline note explaining
when to lower it. Re-verified end to end by actually driving the form in a browser against
all 3 real fixtures with every evaluator (including `grounding_judge`) checked: completed
in 3.8 minutes, all 3 cases succeeded, grounding scored 0.92.

**A second, unrelated issue surfaced during the same debugging session, worth recording
separately since it's operational rather than a code bug:** the `cloud-sql-proxy` tunnel
this environment depends on (see `docs/adr/0009-llm-judge-client-credentials.md`'s
credential-dependency theme) had silently died, and the target system's `/health` endpoint
doesn't check its database connection - so it kept reporting healthy while every real
investigation failed instantly. Restarting the proxy and then the target backend (it
needed a fresh connection pool, not just the proxy back) resolved it. Not a defect in this
platform's own code, but a reminder that this platform's own failure-isolation guarantees
(docs/architecture.md) only cover *this* platform's boundaries - a target agent's own
health check being non-representative of its actual dependencies is exactly the kind of
thing an adapter's caller has no way to see through, and isn't something to try to work
around here.

## What's still open going into Phase 5

- Proving agent-agnosticism with a second/third structurally different adapter is
  unaffected by anything built here - the frontend reads the same generic API shapes
  (`AgentExecutionResult`-derived `CaseRunDetail`, etc.) regardless of which adapter
  produced them, so a new adapter needs no frontend changes, only new data flowing through
  already-built pages.
- Revisiting ADR-0005's synchronous execution model, if real usage volume justifies it, is
  still the one thing that would meaningfully change the run-trigger page's UX (from "wait
  for the page to load" to "watch a status poll").
