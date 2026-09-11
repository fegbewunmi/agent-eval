# 0010. Cloud Run deployment: no core architectural change, two real constraints confirmed

Status: Accepted

## Context

A real external caller - the [Orion Agent Developer Platform](../../../agent-dev-platform),
a separate project's control plane for governing AI agents - needed to integrate against
this platform's real API, not a local instance. ADR-0005 (synchronous execution) had
already anticipated deployment as a future event and left two forward-looking notes worth
revisiting now that it actually happened: whether the synchronous `POST /runs` path would
need to change, and (in ADR-0009) whether the LLM-judge client's `gcloud` CLI dependency
would survive leaving a developer's own machine.

## Decision

Deployed the backend to Cloud Run as `agent-eval-api` (`us-central1`), IAM-authenticated
(`--no-allow-unauthenticated`), backed by a new, isolated database (`agent_eval`) on an
existing Cloud SQL instance owned by the calling platform's own infrastructure (not this
repo's to provision or pay for independently). **The only change to this repository was
one new file, `backend/Dockerfile`** - no application code changed. Full deployment
architecture, configuration, and live verification: `docs/phase-notes/deployment.md`.

This confirms ADR-0005's own prediction was correct: `run_evaluation(...)`'s synchronous,
in-process design needed no redesign to deploy - "moving its invocation behind a queue
later is a call-site change, not a redesign" turned out to mean "moving it behind Cloud
Run is also a call-site change, not a redesign." No task queue was added.

## Alternatives considered

- **Add FastAPI `BackgroundTasks` or a queue before deploying**, per ADR-0005's own
  stated fallback plan. Not needed: real run durations (confirmed live, three real
  incident-investigator runs, 3.5-4.5 minutes each) stay under Cloud Run's default request
  timeout (300s) for datasets of this size. This remains a real, closer-than-comfortable
  margin for larger datasets or slower agents - see Consequences.
- **A dedicated Cloud SQL instance for this platform's own database**, rather than an
  isolated database on infrastructure the calling platform already operates. Rejected as
  the calling platform's decision to make, not this repo's - see its own
  `docs/adrs/0017-shared-cloud-sql-instance-isolated-database.md` for the reasoning
  (this repo has no opinion on where its Postgres physically runs, only that
  `AGENT_EVAL_DATABASE_URL` points at a real, reachable one).

## Consequences

**Confirmed live, exactly as ADR-0009 predicted, not merely still-theoretical**:
`grounding_judge` (the LLM-as-judge evaluator) fails on the deployed service specifically
because the `python:3.12-slim` container has no `gcloud` CLI installed -
`GeminiJudgeClient._access_token()`'s subprocess call raises `FileNotFoundError`, caught
and surfaced per-case as `"could not obtain a Vertex AI access token: [Errno 2] No such
file or directory: 'gcloud'"`. The runner's per-evaluator failure isolation (ADR-0004,
`docs/architecture.md`) worked exactly as designed - the run still completed, the other
evaluator's results are unaffected, and the failure is visible and explicit rather than
silently producing a fabricated score. This is a real, current limitation of the deployed
service, not a hypothetical one anymore - see `docs/phase-notes/deployment.md` for the
exact reproduction and `docs/open-questions.md` #9 (now marked confirmed) for the fix
ADR-0009 already named: swap the `gcloud` subprocess call for the `google-auth` library's
in-process ADC token refresh, which works from any container with valid Application
Default Credentials and needs no CLI binary installed.

**A second, related, real margin worth tracking**: Cloud Run's default request timeout
(300s) was never changed for this deployment. The three real live-verified runs took
209-268 seconds - comfortably under today, but with the calling platform's own
`timeout_seconds` parameter allowing requests up to 240s of *client-side* wait on top of
whatever `POST /runs` itself takes, a larger dataset or a slower target agent could
plausibly exceed 300s. No incident has occurred; this is a forward-looking margin, not a
current bug - `gcloud run services update --timeout` can raise this to a much higher value
(up to 3600s) if real usage ever needs it, without any application-code change.
