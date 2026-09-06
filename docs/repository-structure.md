# Repository Structure

Proposed layout. Nothing here is implemented yet (see `roadmap.md`); this is the target
shape implementation phases will build toward.

```
agent-eval/
├── README.md
├── docs/
│   ├── product-overview.md
│   ├── architecture.md
│   ├── domain-model.md
│   ├── evaluation-architecture.md
│   ├── agent-integration.md
│   ├── tech-stack.md
│   ├── repository-structure.md
│   ├── evaluation-methodology.md
│   ├── roadmap.md
│   ├── open-questions.md
│   └── adr/
│       ├── README.md                 # ADR index
│       ├── template.md
│       ├── 0001-agent-agnostic-adapter-architecture.md
│       ├── 0002-evaluator-type-separation.md
│       ├── 0003-evaluation-dataset-representation.md
│       ├── 0004-immutable-evaluation-runs-and-results.md
│       ├── 0005-synchronous-execution-for-mvp.md
│       ├── 0006-trace-normalization-schema.md
│       ├── 0007-deterministic-evaluation-vs-llm-as-judge.md
│       └── 0008-evaluator-versioning.md
│
├── backend/
│   ├── pyproject.toml
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── main.py                   # FastAPI app entrypoint
│   │   ├── core/                     # config, logging, settings
│   │   ├── db/                       # engine/session setup, declarative base
│   │   ├── models/                   # SQLAlchemy ORM models (domain-model.md)
│   │   ├── schemas/                  # Pydantic request/response + normalized contracts
│   │   │   ├── execution_result.py   # AgentExecutionResult, TraceStep, ToolCallRecord
│   │   │   └── ...
│   │   ├── api/                      # FastAPI routers, one module per resource
│   │   │   ├── agents.py
│   │   │   ├── datasets.py
│   │   │   ├── runs.py
│   │   │   └── comparisons.py
│   │   ├── services/                 # business logic: run orchestration, comparison/diff
│   │   │   ├── runner.py             # run_evaluation(...) — the single execution path
│   │   │   └── comparison.py
│   │   ├── adapters/                 # AgentAdapter base + registry + one dir per agent
│   │   │   ├── base.py               # AgentAdapter ABC
│   │   │   ├── registry.py           # ADAPTER_REGISTRY
│   │   │   └── incident_investigator/
│   │   │       └── adapter.py        # the only file allowed to know about LangGraph
│   │   └── evaluators/               # Evaluator base + registry + implementations by category
│   │       ├── base.py               # Evaluator ABC
│   │       ├── registry.py
│   │       ├── deterministic/
│   │       ├── rule_based/
│   │       ├── llm_judge/            # added in a later phase, not MVP
│   │       └── custom/               # added in a later phase, not MVP
│   └── tests/
│       ├── unit/
│       └── integration/
│
├── frontend/                         # added in a later phase (Phase 4), not MVP
│   ├── package.json
│   ├── app/                          # Next.js App Router pages
│   ├── components/
│   └── lib/                          # typed API client
│
├── datasets/                         # dataset content, authored as files, loaded into the DB
│   └── incident-investigator/
│       └── v1/
│           ├── cases.yaml            # or .json — see ADR-0003
│           └── README.md             # what this dataset covers, how it was built
│
├── scripts/
│   ├── run_eval.py                   # CLI: run a dataset against an agent version
│   ├── load_dataset.py               # import dataset files into the DB
│   └── seed_dev_data.py
│
└── infra/
    └── docker-compose.yml            # local Postgres only — no other infra
```

## Notes on the layout

- **`adapters/` and `evaluators/` are peers of `services/`, not buried inside it** —
  they are the two extension points of the system (new agents, new scoring logic) and
  deserve to be immediately visible at the top of `app/`.
- **`datasets/` is a top-level directory, not under `backend/`**, because dataset content
  is not application code — it's evaluation content that eval engineers (who may not touch
  backend code at all) author and review, likely with its own PR review norms. See
  ADR-0003 for the file-based-authoring-loaded-into-DB decision.
- **`frontend/` is called out as "not MVP"** directly in the tree, matching
  `roadmap.md` — the repository structure documents the target shape, but Phase 1 will not
  populate this directory yet.
- **No `infra/` beyond a local Postgres compose file** — consistent with `tech-stack.md`:
  no Kubernetes manifests, no Terraform, until there's an actual deployment target that
  needs them.
