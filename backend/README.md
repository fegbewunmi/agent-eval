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

## Run the Phase 1 evaluation loop

```bash
uv run python ../scripts/run_eval.py \
  --dataset-file ../datasets/stub-agent/smoke-v1/cases.yaml \
  --agent-version v1
```

This loads the dataset, registers the stub agent + version + deterministic evaluators if
they don't already exist, runs the dataset through `app/adapters/stub_agent`, and prints a
per-case, per-dimension summary.

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
