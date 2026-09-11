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
│   ├── Dockerfile                    # Cloud Run deployment - the only file deployment added, see ADR-0010
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
│   │   ├── api/                      # FastAPI routers
│   │   │   ├── deps.py               # DB session dependency
│   │   │   ├── runs.py               # trigger/get/list runs, case detail, compare
│   │   │   └── catalog.py            # read-only agents/datasets/evaluators browsing (Phase 4)
│   │   ├── services/                 # business logic: run orchestration, comparison/diff
│   │   │   ├── runner.py             # run_evaluation(...) - the single execution path
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
│   │       ├── llm_judge/            # Phase 3 - grounding_judge + the judge model client
│   │       └── custom/               # not yet needed - add when a concrete case arises
│   └── tests/
│       ├── unit/
│       └── integration/
│
├── frontend/                         # Phase 4 - Next.js App Router, server components only
│   ├── package.json
│   ├── app/                          # Next.js App Router pages
│   ├── components/
│   └── lib/                          # typed API client
│
├── datasets/                         # dataset content, authored as files, loaded into the DB
│   └── incident-investigator/
│       └── v1/
│           ├── cases.yaml            # or .json - see ADR-0003
│           └── README.md             # what this dataset covers, how it was built
│
├── scripts/
│   ├── run_eval.py                   # CLI: run a dataset against an agent version
│   ├── load_dataset.py               # import dataset files into the DB
│   └── seed_dev_data.py
│
└── infra/
    └── docker-compose.yml            # local Postgres only - the deployed backend uses a
                                       # database on infrastructure the calling platform
                                       # operates, not anything provisioned from this repo -
                                       # see docs/phase-notes/deployment.md
```

## Notes on the layout

- **`adapters/` and `evaluators/` are peers of `services/`, not buried inside it** -
  they are the two extension points of the system (new agents, new scoring logic) and
  deserve to be immediately visible at the top of `app/`.
- **`datasets/` is a top-level directory, not under `backend/`**, because dataset content
  is not application code - it's evaluation content that eval engineers (who may not touch
  backend code at all) author and review, likely with its own PR review norms. See
  ADR-0003 for the file-based-authoring-loaded-into-DB decision.
- **`frontend/` has no client components** as of Phase 4 - every page is a Server
  Component that fetches directly from the backend API, and the two mutating flows
  (trigger a run, pick two runs to compare) use native HTML forms with Server Actions
  instead of client-side state or a fetch library. This is a direct instance of
  `tech-stack.md`'s deferred styling/state-management decision: no state-management
  library was needed because nothing in this UI needs client-side state yet. See
  `docs/phase-notes/phase-4.md`.
- **`infra/` still holds only the local Postgres compose file, even after a real
  deployment target now exists** - deliberately. No Kubernetes manifests, no Terraform,
  no deploy scripts were added to this repo; deploying the backend needed exactly one
  new file (`backend/Dockerfile`) plus a small number of `gcloud` commands run once,
  documented in `docs/phase-notes/deployment.md` rather than checked in as
  infrastructure-as-code this project doesn't otherwise need.
