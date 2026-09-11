# Deployment notes - Cloud Run

Status: deployed and live. This is not a numbered phase - the design brief's five planned
phases (`docs/roadmap.md`) were already complete and are described in
`docs/phase-notes/phase-1.md` through `phase-5.md`, which remain an accurate record of
**what was true during each of those phases** (all local, unauthenticated, no deployment
target). This document describes **current system state**: a real Cloud Run deployment,
added afterward, for a real reason. Where this document and an earlier phase note appear
to disagree (e.g. "no deployment exists" in `phase-notes/phase-1.md` or
`docs/open-questions.md`'s original framing of item #9), this document is the current
truth and the earlier one is a historical snapshot, not a mistake being corrected.

## Why deployment was done

A real external system - the [Orion Agent Developer Platform](../../../agent-dev-platform),
a separate project implementing an agent governance control plane - needed to integrate
against this platform's real evaluation API as part of its own Phase 3 (evaluation policy
gates and promotion eligibility). That integration needed a genuinely reachable, real
service to call, not a mocked stand-in or a description of intended behavior. Deploying
this backend was the smallest way to make that real.

## Current deployment status

| Aspect | Value |
|---|---|
| Service | `agent-eval-api` |
| Platform | Cloud Run (`us-central1`) |
| Project | `ai-ops-center-eb26` (the calling platform's GCP project, not one this repo owns) |
| URL | `https://agent-eval-api-zndywutdxa-uc.a.run.app` |
| Image | `us-central1-docker.pkg.dev/ai-ops-center-eb26/ai-ops-images/agent-eval-api:v1` |
| Auth | IAM-protected (`--no-allow-unauthenticated`) - no public access |
| Frontend | **Not deployed.** Only the backend API has a live target. |
| Request timeout | 300s (Cloud Run default, unchanged) - see "Synchronous POST /runs timeout implications" below |

## Cloud Run architecture

```
                          Google-signed ID token (OIDC)
                                     |
                                     v
  Orion Agent Developer Platform --------> agent-eval-api (Cloud Run, us-central1)
  (external caller, separate repo)             |
                                                |  Cloud SQL native connector
                                                v
                                    ai-ops-db (Cloud SQL Postgres)
                                    database: agent_eval (isolated)
                                    user: agent_eval_app (scoped)
```

`agent-eval-api` is a single stateless container - the same `run_evaluation(...)`
synchronous-execution design as local development (ADR-0005), unchanged. No queue, no
separate worker process, no orchestration beyond what Cloud Run itself provides.

## Exact changes required

**One new file in this repository: `backend/Dockerfile`.**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY app/ app/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Nothing else in this repository changed. No application code, no dependency, no schema,
no evaluator, no adapter was touched.

## What stayed unchanged

- **`run_evaluation(...)` and the entire synchronous execution model (ADR-0005)** - `POST
  /runs` still blocks until the run completes, exactly as it does locally. No task queue
  was added to deploy this.
- **Every evaluator, adapter, and the runner's failure-isolation design** - unmodified,
  and (see "Bugs/issues discovered" below) proven to behave correctly under a real
  failure encountered only once deployed.
- **The database schema and Alembic migrations** - applied to the new database exactly as
  they would be applied locally, same migration files, same `alembic upgrade head`.
- **Local development** - `backend/README.md`'s and `frontend/README.md`'s instructions
  are unchanged; nothing about running this platform on a developer's own machine
  requires touching anything related to Cloud Run.
- **The frontend** - not deployed, not touched, not affected.

## Auth model

**No application code changes.** Authentication is enforced entirely at the platform
level - Cloud Run's own IAM, not anything this codebase implements or is aware of:

- The service was deployed with `--no-allow-unauthenticated`.
- A dedicated service account (owned by the calling platform, `agent-dev-platform-caller`)
  was granted `roles/run.invoker` on this specific Cloud Run service.
- Every request must carry a valid Google-signed ID token for a principal holding that
  role, with `audience` matching this service's URL - Cloud Run validates this before the
  request ever reaches the FastAPI application. An unauthenticated request gets Cloud
  Run's own `403 Forbidden`, never reaching `app/main.py`.

This means `docs/product-overview.md`'s original MVP framing ("a single static API key is
enough for an internal tool with no multi-tenancy") was never actually implemented in
code, and deployment didn't implement it either - real auth arrived as an infrastructure
decision external to the application, not as an app-level API key check.

## Database/network model

- **No new Cloud SQL instance.** The `agent_eval` database and a scoped `agent_eval_app`
  user were created on an existing Cloud SQL instance already operated by the calling
  platform's own infrastructure (not provisioned, owned, or paid for by this repository).
- **Connectivity**: Cloud Run's native Cloud SQL connector (`--add-cloudsql-instances`),
  the same mechanism used by other services on that same GCP project - `psycopg`/
  SQLAlchemy connect over a Unix socket at `/cloudsql/<connection-name>`, no VPC
  configuration needed in this repo.
- **Isolation, precisely characterized**: `agent_eval_app` can technically open a
  connection to that instance's *other* database (a real Cloud SQL Postgres limitation -
  any `gcloud sql users create` user is a member of `cloudsqlsuperuser`, which bypasses
  ordinary `REVOKE CONNECT`), but has no `SELECT`/`INSERT`/`UPDATE`/`DELETE` grant on any
  table there - verified live, `permission denied` on every attempted query against the
  other database's tables. The real isolation boundary is object-level grants, not
  connection-level, and this was confirmed rather than assumed.

## Secrets/configuration management

- **`AGENT_EVAL_DATABASE_URL`** is stored in Secret Manager and injected as an environment
  variable at deploy time (`--set-secrets`) - never baked into the image, never committed.
  Value shape: `postgresql+psycopg://agent_eval_app:<password>@/agent_eval?host=/cloudsql/<connection-name>`.
- No other secret or API key exists for this service - it has no outbound credential of
  its own beyond the Cloud SQL connection (Vertex AI calls, where they work at all - see
  Known Limitations - rely on Application Default Credentials, not a stored secret).
- **No `.env` file, no secret, was added to this repository for deployment.** Everything
  deployment-specific lives in Secret Manager and the `gcloud run deploy` command itself
  (below), not in version control.

## Local vs. deployed execution

| | Local | Deployed |
|---|---|---|
| Entry point | `uv run uvicorn app.main:app --port 8000` | Same `uvicorn app.main:app`, container port 8080 |
| Database | Local Postgres via `docker-compose.yml` | Cloud SQL, isolated database, Cloud Run's native connector |
| Auth | None - open to any local caller | Cloud Run IAM - every request needs a real ID token |
| `POST /runs` behavior | Synchronous, blocks until complete | **Identical** - synchronous, blocks until complete |
| `grounding_judge` (LLM-as-judge) | Works - `gcloud` CLI present on a developer's machine, real ADC | **Fails** - see Known Limitations |
| Frontend | Runs locally against either backend | Not deployed; there is no way to browse the deployed backend's data in the UI today |

## Synchronous `POST /runs` timeout implications

ADR-0005 already anticipated this and left `BackgroundTasks` as a documented fallback if
API-triggered run duration ever became a real problem. Deployment didn't change the
runner, but it did introduce a concrete, external time limit that didn't meaningfully
exist for a local `uvicorn` process: **Cloud Run's default request timeout is 300
seconds**, left unchanged for this deployment.

Real, live-measured run durations against the deployed service (three separate real runs
of the real `incident-investigator` agent, 3 cases each): **209s, 219s, and 258s** - all
comfortably under 300s today, but with real per-case latency in the 60-120 second range,
a dataset with more cases, or a slower target agent, could plausibly exceed it. This is a
**named, forward-looking margin, not a current incident** - `gcloud run services update
agent-eval-api --timeout=<seconds>` can raise this to as much as 3600s with no application
change if real usage ever needs it. See [ADR-0010](../adr/0010-cloud-run-deployment.md).

## Deployment/redeployment steps

Not automated, not checked into this repo as scripts (per `tech-stack.md`'s "no
speculative infrastructure" stance) - run manually, once, and reproduced here exactly:

```bash
# 1. Build and push the image (Cloud Build - no local Docker daemon required)
cd backend
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/ai-ops-center-eb26/ai-ops-images/agent-eval-api:v1 .

# 2. Deploy (idempotent - re-running updates the existing service)
gcloud run deploy agent-eval-api \
  --image=us-central1-docker.pkg.dev/ai-ops-center-eb26/ai-ops-images/agent-eval-api:v1 \
  --region=us-central1 \
  --no-allow-unauthenticated \
  --add-cloudsql-instances=ai-ops-center-eb26:us-central1:ai-ops-db \
  --set-secrets=AGENT_EVAL_DATABASE_URL=agent-eval-db-url:latest \
  --max-instances=3 \
  --port=8080

# 3. Apply any new Alembic migrations against the deployed database (via Cloud SQL proxy)
cloud-sql-proxy ai-ops-center-eb26:us-central1:ai-ops-db --port 5434 &
cd backend
AGENT_EVAL_DATABASE_URL="postgresql+psycopg://agent_eval_app:<password>@127.0.0.1:5434/agent_eval" \
  uv run alembic upgrade head
```

Redeploying after a code change is step 1 + step 2 with a new image tag; a schema change
additionally needs step 3.

## Tests

**No changes to the automated test suite for this deployment** - 57 backend tests (per
`phase-notes/phase-5.md`), all still passing, all still mocking every external call. The
deployment itself was verified live (below), not through the automated suite, since there
is nothing about "is the deployed service reachable and correctly configured" that a unit
or integration test running against a local database would meaningfully exercise.

## Live verification

All performed against the real deployed `agent-eval-api`, with real Google-signed ID
tokens (via `google.auth.impersonated_credentials`, no service-account key file ever
downloaded):

1. **Health/startup**: `GET /health` unauthenticated → `403` (Cloud Run IAM correctly
   blocking); authenticated → `200 {"status": "ok"}`.
2. **Database connectivity**: `GET /agents`, `GET /datasets`, `GET /evaluators` - all
   return real, correctly-seeded catalog data from the `agent_eval` Cloud SQL database.
3. **A real evaluation run against a real target**: `incident-investigator` (real
   LangGraph + Vertex AI agent, itself deployed separately as `ai-ops-api`) - three
   separate real runs, one against `stub-agent` (no external dependency) and two full
   3-case `incident-investigator` runs, real durations 209-268 seconds, correct
   `dimension_stats`, correct per-case results, correct failure isolation on the one
   evaluator that couldn't complete (below).
4. **Isolation boundary**: confirmed live that `agent_eval_app` cannot read any table in
   the instance's other database (`permission denied`), while correctly reading/writing
   its own.

## Bugs/issues discovered

1. **`grounding_judge` fails on the deployed service - confirmed, reproducible, root
   cause identified precisely.** `GeminiJudgeClient._access_token()` shells out to
   `gcloud auth application-default print-access-token` (ADR-0009); the deployed
   container (`python:3.12-slim`) has no `gcloud` CLI installed. Reproduced live:
   `evaluation_results` for the case shows
   `grounding_judge | None | Evaluator raised an exception: could not obtain a Vertex AI
   access token: [Errno 2] No such file or directory: 'gcloud'`. The runner's
   per-evaluator failure isolation (`docs/architecture.md`) worked exactly as designed -
   the run still completed with `status: completed_with_errors`, every other evaluator's
   results were correct and unaffected, and the failure is explicit and inspectable
   rather than silently missing or fabricated. This is the exact failure mode
   `ADR-0009`'s own Consequences section predicted before any deployment existed to test
   it against - now confirmed, not hypothetical. See `docs/open-questions.md` #9 and
   [ADR-0009](../adr/0009-llm-judge-client-credentials.md)'s amendment. **Not yet fixed** -
   the fix (swap the `gcloud` subprocess call for the `google-auth` library's in-process
   ADC token refresh) was already named in ADR-0009 before deployment; it remains an open
   task, now with confirmed urgency rather than speculative risk.
2. **A configuration gap in the deployed database's seed data, not a code bug**: the
   `grounding_judge` `Evaluator` row's `config` was seeded without a `project_id` key
   (this platform's own `scripts/run_eval.py` only sets it when the `--judge-project-id`
   CLI flag is passed; the one-off script used to seed the deployed database's catalog
   omitted it). Surfaced as a clean `KeyError: 'project_id'`, caught by the same
   per-evaluator failure isolation. Fixed directly in the deployed database
   (`UPDATE evaluators SET config = '{"project_id": "ai-ops-center-eb26"}' WHERE key =
   'grounding_judge'`) once identified - this was necessary groundwork to isolate and
   confirm bug #1 above as the real, remaining blocker, distinct from this one-off seed
   gap.

## Current limitations

- **`grounding_judge` (the LLM-as-judge, `grounding` dimension) does not produce real
  scores on the deployed service** until the `google-auth` fix (above) ships. Every other
  evaluator (`completion_check`, `latency_threshold`, `required_tool_calls`,
  `no_redundant_tool_calls`, `final_output_contains_keywords`,
  `retrieved_text_contains_keywords`, `structured_field_exact_match`,
  `structured_field_minimum`) works correctly and was live-verified.
- **No frontend is deployed** - inspecting a deployed run's full detail (case-by-case
  trace, tool calls, per-evaluator reasoning) requires calling the API directly
  (`GET /runs/{id}/cases/{case_id}`) rather than using the UI.
- **300-second request timeout** is a real, named margin for larger datasets or slower
  agents - see "Synchronous POST /runs timeout implications" above. Not currently hit; not
  proactively raised, since no real usage has needed it yet.
- **No CI/CD** - deployment is a manual, documented procedure (above), consistent with
  this project's stated preference against speculative infrastructure until a concrete
  need (e.g. deployment happening often enough to justify automating it) actually
  appears.
- **Deployed-database seed data is maintained ad hoc**, not through this repository's own
  `scripts/` - the calling platform's own one-off seeding is what currently populates the
  deployed `agent_eval` database's catalog (agents, datasets, evaluators). If this
  platform's own `seed_dev_data.py`/`load_dataset.py` scripts are ever intended to be the
  source of truth for the deployed instance too, that's a real, not-yet-done integration
  step, not something implied by anything in this document.
