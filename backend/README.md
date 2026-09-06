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
  --timeout-seconds 240
```

Either way this loads the dataset, registers the agent/version/evaluators if they don't
already exist, runs the dataset through the selected adapter, and prints a per-case,
per-dimension summary.

## Run the API

```bash
uv run uvicorn app.main:app --port 8080
```

- `POST /runs` — trigger a run (`agent_version_id`, `dataset_id`, `evaluator_ids`); runs
  synchronously within the request (ADR-0005).
- `GET /runs/{id}` — run summary: status, per-dimension mean scores, case list.
- `GET /runs/{id}/cases/{case_run_id}` — full case detail: input, expected, output, trace,
  tool calls, and every evaluator's result.
- `GET /runs/compare?run_a_id=...&run_b_id=...` — per-case, per-dimension regressions and
  improvements between two runs over the same dataset.

There's no CRUD API for `Agent`/`Dataset`/`Evaluator` yet — register those via
`app/services/seed.py` (as `scripts/run_eval.py` does) or a DB client directly.

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
