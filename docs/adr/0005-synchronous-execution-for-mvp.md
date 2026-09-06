# 0005. Synchronous execution for MVP

Status: Accepted

## Context

Running an `EvaluationRun` means invoking an agent adapter once per case in a dataset,
which can be slow (agent calls, possibly LLM-as-judge calls later) and could in principle
run for minutes. A "proper" production system might reach for a task queue (Celery, RQ,
arq) and worker processes so the API request that triggers a run returns immediately and
work happens asynchronously and can be horizontally scaled. The design brief explicitly
warns against unnecessary distributed systems and premature infrastructure.

## Decision

For MVP (Phases 1–4 of `docs/roadmap.md`), evaluation runs execute **synchronously and
in-process**: a single `run_evaluation(...)` function (`app/services/runner.py`) is called
either directly from a CLI script or from a FastAPI request handler, executes all cases
(optionally with bounded `asyncio` concurrency across cases within one run), and returns
once the run is complete. No message broker, no separate worker process, no job queue.

If run duration becomes a real problem for the API-triggered path specifically (long HTTP
requests are awkward), the fallback within this same architecture is FastAPI
`BackgroundTasks` (still in-process, still no new infrastructure) — not a queue.

## Alternatives considered

- **Task queue + worker pool (Celery/RQ/arq) from the start.** Rejected for MVP: adds a
  broker (Redis/RabbitMQ) and a worker deployment to operate, for a scale (internal tool,
  small datasets, infrequent runs) that doesn't need it. This is exactly the "unnecessary
  distributed systems" the design brief asks to avoid.
- **Fully async/streamed run status via WebSockets.** Rejected for the same reason —
  polling `GET /runs/{id}` is sufficient for MVP run durations and is far simpler to
  implement and reason about.

## Consequences

- The runner's internal design (`docs/architecture.md`) does not depend on being called
  synchronously — `run_evaluation(...)` takes IDs and returns/persists a result, so moving
  its invocation behind a queue later is a call-site change, not a redesign, if Phase 5
  finds real evidence this is needed.
- Very large datasets or very slow agents will make the synchronous path (or even
  `BackgroundTasks`) impractical eventually. This is accepted as a known, deferred limit —
  explicitly revisited in Phase 5 of `docs/roadmap.md`, with actual run-volume evidence
  informing that decision rather than speculation now.
- Because there's no distributed worker fleet, there's also no need yet for idempotency
  keys, distributed locks, or job-retry infrastructure — all of which would otherwise be
  required and are correctly deferred alongside the queue itself.
