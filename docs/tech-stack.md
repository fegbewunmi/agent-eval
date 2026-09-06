# Technical Stack

The stack was specified up front (Python, FastAPI, PostgreSQL, SQLAlchemy, Next.js,
TypeScript). This document records what's added on top and, just as importantly, what was
deliberately **not** added.

## Backend

- **Python 3.12+**, **FastAPI** for the HTTP API.
- **SQLAlchemy 2.0** (typed, declarative) as the ORM; **Alembic** for migrations — the
  standard, boring pairing, no reason to deviate.
- **Pydantic v2** for request/response schemas and for the `AgentExecutionResult` /
  `TraceStep` / `ToolCallRecord` normalized-data contracts described in
  `agent-integration.md`. Reusing Pydantic (already a FastAPI dependency) instead of hand
  rolling validation.
- **pytest** for backend tests.
- Execution/orchestration ("the runner") is plain Python — synchronous function calls,
  optionally using `asyncio` for concurrent case execution within a single run. No task
  queue (Celery, RQ, arq), no message broker, no Kubernetes. See ADR-0005.
- **httpx** only if/when an adapter needs to call a target agent over HTTP (e.g. the
  Incident Investigation Platform if it's deployed as a service). Not a core platform
  dependency — it lives in the adapter that needs it.

## Frontend

- **Next.js** (App Router) + **TypeScript**. Server-rendered pages are sufficient; no need
  for a separate SPA build pipeline.
- No state-management library beyond React's built-ins / server components — the frontend
  is a thin client over the API with no complex client-side state to justify Redux/Zustand
  etc. Revisit only if the comparison/trace-viewer UI turns out to need it.
- Styling/component library choice is deferred to the frontend implementation phase
  (Phase 4) — not an architectural decision worth fixing now.

## Database

- **PostgreSQL**, using **JSONB** columns for the genuinely variable-shape data called out
  in `domain-model.md` (`EvaluationCase.input/expected`, `CaseRun.raw_output` /
  `normalized_trace`, `ToolCall.arguments/result`, `Evaluator.config`,
  `EvaluationResult.raw_output`). Everything with a fixed, known shape is a normal
  relational column. This mirrors how the schema is already presented in
  `domain-model.md` — no separate document/NoSQL store is introduced for this.

## Explicitly not added, and why

- **No task queue / worker infrastructure (Celery, RQ, arq, Ray).** MVP dataset sizes and
  run frequency don't justify the operational cost of a broker + worker fleet. The runner
  is designed so this can be introduced later without changing the domain model — see
  ADR-0005.
- **No Kubernetes or container orchestration.** A single backend process and a Postgres
  instance are sufficient; this is an internal tool, not a multi-tenant service.
- **No LangGraph, or any agent-orchestration framework, inside the evaluation platform.**
  The target Incident Investigation Platform uses LangGraph; the evaluation platform must
  not, precisely because it evaluates arbitrary agents and must not be built around any one
  of their frameworks. See ADR-0001.
- **No vector database / embeddings infrastructure** unless and until a custom or
  LLM-judge evaluator specifically needs semantic similarity — not a foreseeable MVP need,
  and not worth standing up speculatively.
- **No auth provider / identity system.** A single static API key is enough for an
  internal tool with no multi-tenancy (see `product-overview.md`).
- **No API gateway, service mesh, or multi-service split.** One backend service, one
  frontend, one database.
