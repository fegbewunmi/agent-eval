# Backend

FastAPI + SQLAlchemy + PostgreSQL backend for the Agent Evaluation Platform. See
`../docs/` for architecture and design docs; this file is just setup/run instructions.

## Setup

Requires a running PostgreSQL instance (see `../infra/docker-compose.yml` if you don't
have one locally) and [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv sync --group dev
cp .env.example .env   # then edit AGENT_EVAL_DATABASE_URL if needed
createdb agent_eval_dev  # or: docker compose -f ../infra/docker-compose.yml up -d
uv run alembic upgrade head
```

## Run an evaluation via the CLI

Against the stub agent (no external dependencies):

```bash
uv run python ../scripts/run_eval.py \
  --dataset-file ../datasets/stub-agent/smoke-v1/cases.yaml \
  --agent-version v1
```

Against the real Incident Investigation Platform (requires that system running locally —
see its own README — and costs real LLM API calls):

```bash
uv run python ../scripts/run_eval.py \
  --dataset-file ../datasets/incident-investigator/smoke-v1/cases.yaml \
  --agent-name incident-investigator --adapter-key incident-investigator \
  --agent-version v1 \
  --agent-config '{"base_url": "http://localhost:8080", "max_wait_seconds": 180}' \
  --timeout-seconds 240 \
  --judge-project-id ai-ops-center-eb26   # optional: also run grounding_judge (real Vertex AI calls, ADR-0009)
```

Against the real Document Q&A RAG platform (requires that system running locally - see its
own README - and costs real OpenAI API calls):

```bash
uv run python ../scripts/run_eval.py \
  --dataset-file ../datasets/document-qa/resume-v1/cases.yaml \
  --agent-name document-qa --adapter-key document-qa \
  --agent-version v1 \
  --agent-config '{"base_url": "http://localhost:3001"}' \
  --timeout-seconds 60 \
  --judge-project-id ai-ops-center-eb26   # optional: also run grounding_judge (real Vertex AI calls, ADR-0009)
```

Either way this loads the dataset, registers the agent/version/evaluators if they don't
already exist, runs the dataset through the selected adapter, and prints a per-case,
per-dimension summary. `--judge-project-id` needs the `gcloud` CLI authenticated with
Vertex AI access in that project (see ADR-0009); omit it to skip the grounding judge.

## Load a dataset without running it

```bash
uv run python ../scripts/load_dataset.py --dataset-file ../datasets/<agent>/<name>/cases.yaml
```

See `../docs/dataset-authoring.md` for the file format and what each evaluator's
`expected` needs.

## Run the API

```bash
uv run uvicorn app.main:app --port 8000
```

Port 8000, not 8080 - the Incident Investigation Platform's own backend commonly runs on
8080 (see its README), and the two are often running side by side during development.

- `POST /runs` - trigger a run (`agent_version_id`, `dataset_id`, `evaluator_ids`); runs
  synchronously within the request (ADR-0005).
- `GET /runs?dataset_id=...&agent_version_id=...` - list recent runs, most recent first.
- `GET /runs/{id}?tag=<tag>` - run summary: status, per-dimension mean scores, case list;
  optionally restricted to cases carrying `<tag>` (docs/evaluation-methodology.md).
- `GET /runs/{id}/cases/{case_run_id}` - full case detail: input, expected, output, trace,
  tool calls, and every evaluator's result.
- `GET /runs/compare?run_a_id=...&run_b_id=...` - per-case, per-dimension regressions and
  improvements between two runs over the same dataset.
- `GET /agents`, `GET /datasets`, `GET /datasets/{id}`, `GET /evaluators` - read-only
  catalog browsing (Phase 4), for the frontend's dropdowns and listing pages.

There's no create/update/delete API for `Agent`/`Dataset`/`Evaluator` - register those via
`app/services/seed.py` (as `scripts/run_eval.py` does) or `scripts/load_dataset.py`
(datasets, per ADR-0003).

## Tests

```bash
uv run pytest
```

Integration tests use a dedicated `agent_eval_test` database on the same Postgres
instance (created automatically on first run) and roll back each test's transaction, so
they don't require a separate test-database lifecycle to manage.

## Migrations

```bash
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```
