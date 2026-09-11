# Architecture Decision Records

Each ADR captures one decision that had genuine alternatives worth recording, per the
design brief's instruction: "where there are meaningful alternatives, record the decision
and tradeoff rather than pretending there is one obvious answer."

| # | Title | Status |
|---|---|---|
| [0001](0001-agent-agnostic-adapter-architecture.md) | Agent-agnostic adapter architecture | Accepted |
| [0002](0002-evaluator-type-separation.md) | Evaluator type separation | Accepted |
| [0003](0003-evaluation-dataset-representation.md) | Evaluation dataset representation | Accepted |
| [0004](0004-immutable-evaluation-runs-and-results.md) | Immutable evaluation runs and results | Accepted |
| [0005](0005-synchronous-execution-for-mvp.md) | Synchronous execution for MVP | Accepted |
| [0006](0006-trace-normalization-schema.md) | Trace normalization schema | Accepted |
| [0007](0007-deterministic-evaluation-vs-llm-as-judge.md) | Deterministic evaluation vs. LLM-as-judge sequencing | Accepted |
| [0008](0008-evaluator-versioning.md) | Evaluator versioning | Accepted |
| [0009](0009-llm-judge-client-credentials.md) | LLM-judge client and credential strategy | Accepted |
| [0010](0010-cloud-run-deployment.md) | Cloud Run deployment: no core architectural change, two real constraints confirmed | Accepted |

New ADRs should use [template.md](template.md) and be numbered sequentially. An ADR's
status can move from `Proposed` → `Accepted` → `Superseded by NNNN`, but its content
should not be rewritten after acceptance - record a new ADR that supersedes it instead.
