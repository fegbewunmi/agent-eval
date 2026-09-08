# Dataset Authoring

How to add or edit an evaluation dataset. See ADR-0003 for why datasets are authored as
files and loaded into the database, rather than authored through an API.

## File layout

One directory per dataset under `datasets/<agent-key>/<dataset-name>/`:

```
datasets/<agent-key>/<dataset-name>/
├── cases.yaml   # required
└── README.md    # required - what this dataset covers, how it was built
```

## `cases.yaml` shape

```yaml
dataset:
  name: <unique dataset name>       # used as the DB Dataset.name
  description: <what this dataset tests>

cases:
  - key: <unique key within this dataset>   # stable id, used in reports/comparisons
    input: <dict>                            # whatever the target adapter needs - see its docstring
    expected: <dict>                         # see "expected shapes by evaluator" below
    tags: [<string>, ...]                    # optional; used for segmented reporting
    metadata: <dict>                         # optional; free-form (source, author, notes)
```

`input` and `expected` have no platform-enforced schema (ADR-0003) - their shape is
defined by the adapter (for `input`) and by whichever evaluators you configure for the run
(for `expected`). Check the target adapter's module docstring for its `input` shape (e.g.
`app/adapters/incident_investigator/adapter.py`) before writing cases against it.

## `expected` shapes by evaluator

Only set the keys your configured evaluators actually consume - an evaluator with nothing
to check reports "not applicable" (excluded from aggregate scores, docs/evaluation-methodology.md), it doesn't fail the case.

| Evaluator key | `expected` key it reads | Shape |
|---|---|---|
| `structured_field_exact_match` | `structured_output` | `{field: expected_value, ...}` - exact match |
| `structured_field_minimum` | `structured_output_minimums` | `{field: minimum_number, ...}` |
| `latency_threshold` | `max_latency_ms` | number |
| `required_tool_calls` | `required_tools` | `[tool_name, ...]` |
| `completion_check` | *(none)* | always applicable - reads `CaseRun.status` directly |
| `no_redundant_tool_calls` | *(none)* | always applicable - reads the trace's tool calls directly |
| `grounding_judge` | *(none)* | always applicable if the agent's `structured_output` has a `supporting_evidence` list |

## Loading a dataset

```bash
uv run python scripts/load_dataset.py --dataset-file datasets/<agent-key>/<dataset-name>/cases.yaml
```

Idempotent: re-running upserts cases by `(dataset name, case key)` - editing a case's
`input`/`expected`/`tags` and re-loading updates it in place. This is also what
`scripts/run_eval.py` does automatically before running, so a separate load step is only
needed if you want to load without running (e.g. to review what a change would affect via
the API before triggering a run).

## Tags

Tags exist for segmented reporting - `GET /runs/{id}?tag=<tag>` restricts a run's
per-dimension stats and case list to cases carrying that tag. Use them for scenario
categories worth reporting separately (e.g. `high-severity`, `multi-tool`), not as a
general-purpose free-text field - `metadata` is for that.

## Adding cases to an existing dataset

Add entries to `cases.yaml` under the existing `dataset:` block and re-run the load
script (or `run_eval.py`). This changes `EvaluationRun.dataset_snapshot_hash` for any
future run, which is what lets a comparison between an old run and a new one detect and
flag dataset drift (ADR-0003, docs/evaluation-methodology.md) - expected and correct
behavior, not a bug to work around.

## Adding a new dataset for a new adapter

1. Read the target adapter's module docstring for its `input` shape.
2. Write 5–15 cases covering: the common/easy cases, at least one genuinely ambiguous
   case, and (recommended, see `datasets/stub-agent/smoke-v1/README.md` for the pattern)
   one or two cases that deliberately exercise failure isolation if the adapter supports
   injecting a failure.
3. Where possible, base `expected` on an existing ground-truth source rather than
   inventing it - see `datasets/incident-investigator/smoke-v1/README.md` for an example
   of reusing a target system's own committed eval fixtures.
4. Write the dataset's `README.md` explaining what it covers and why.
