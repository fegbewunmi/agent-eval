# Agent Evaluation Platform

A production-style platform for answering one question, reliably and repeatably:

> **When I change an AI agent, did it actually get better?**

See [`docs/roadmap.md`](docs/roadmap.md) for the phased implementation plan and
[`docs/open-questions.md`](docs/open-questions.md) for unresolved decisions.

**Status: Phase 2 complete** — a real adapter for the Incident Investigation Platform
(github.com/fegbewunmi/ai-operations-center) runs live investigations through
`POST /runs`, `GET /runs/{id}`, `GET /runs/{id}/cases/{case_run_id}`, and
`GET /runs/compare`, scored across task_correctness, completion, latency, tool_selection,
and tool_efficiency. Verified against the real system (real Gemini/Vertex AI calls, real
Cloud SQL), not just a mock of it. No UI yet — no LLM-as-judge evaluators yet. See
[`docs/phase-notes/phase-2.md`](docs/phase-notes/phase-2.md) (and
[`phase-1.md`](docs/phase-notes/phase-1.md)) and [`backend/README.md`](backend/README.md)
to run it.

## Start here

| Doc | Purpose |
|---|---|
| [docs/product-overview.md](docs/product-overview.md) | Problem, users, workflows, MVP scope |
| [docs/architecture.md](docs/architecture.md) | Components, responsibilities, data flow, failure boundaries |
| [docs/domain-model.md](docs/domain-model.md) | Entities, relationships, and changes to the proposed model |
| [docs/evaluation-architecture.md](docs/evaluation-architecture.md) | Evaluator categories and when to use each |
| [docs/agent-integration.md](docs/agent-integration.md) | The adapter interface that keeps the platform agent-agnostic |
| [docs/tech-stack.md](docs/tech-stack.md) | Technology choices and why nothing more was added |
| [docs/repository-structure.md](docs/repository-structure.md) | Proposed repo layout |
| [docs/evaluation-methodology.md](docs/evaluation-methodology.md) | How agent quality is measured without a single misleading score |
| [docs/roadmap.md](docs/roadmap.md) | Phased implementation plan, starting from a deterministic-only slice |
| [docs/open-questions.md](docs/open-questions.md) | Assumptions and unresolved questions, tracked explicitly |
| [docs/adr/README.md](docs/adr/README.md) | Architecture Decision Record index |

## Guiding constraints

These were set at the outset and shape every decision in this repo:

- Not a commercial SaaS product: no billing, no organizations, no complex RBAC.
- No Kubernetes, no distributed task queues, no unnecessary infrastructure.
- The evaluation platform does **not** use LangGraph, even though the first target system
  (an Incident Investigation Platform) does. The platform must stay agent-agnostic.
- Prefer simple, explicit abstractions over speculative generality.
- Where a decision has real tradeoffs, it is recorded (see `docs/adr/`) rather than
  silently picked.
