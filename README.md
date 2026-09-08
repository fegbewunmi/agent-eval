# Agent Evaluation Platform

A production-style platform for answering one question, reliably and repeatably:

> **When I change an AI agent, did it actually get better?**

See [`docs/roadmap.md`](docs/roadmap.md) for the phased implementation plan and
[`docs/open-questions.md`](docs/open-questions.md) for unresolved decisions.

**Status: all planned phases (0-5) complete.** Two real, structurally different agents are
integrated end to end: the Incident Investigation Platform
(github.com/fegbewunmi/ai-operations-center, a multi-agent LangGraph investigation) and
Document Q&A (github.com/fegbewunmi/document-qa, a single-call RAG app) - both run
through the exact same adapter/runner/evaluator/persistence/comparison pipeline and the
same Next.js frontend, with zero platform-core changes needed to support the second one.
Evaluated dimensions include task_correctness, completion, latency, tool_selection,
tool_efficiency, grounding (a real LLM-as-judge evaluator backed by Vertex AI Gemini), and
retrieval. Verified against both real systems throughout - see
[`docs/phase-notes/phase-5.md`](docs/phase-notes/phase-5.md) (and
[`phase-4.md`](docs/phase-notes/phase-4.md) / [`phase-3.md`](docs/phase-notes/phase-3.md) /
[`phase-2.md`](docs/phase-notes/phase-2.md) / [`phase-1.md`](docs/phase-notes/phase-1.md)),
[`backend/README.md`](backend/README.md), and [`frontend/README.md`](frontend/README.md)
to run it. No further phases are planned.

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
| [docs/dataset-authoring.md](docs/dataset-authoring.md) | How to write and load an evaluation dataset |
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
