# Agent Integration Architecture

## Goal

Very different agents - a LangGraph-based multi-agent incident investigator today; a RAG
app, a customer-support agent, a coding agent, or a SQL agent tomorrow - must be evaluable
through one platform without the platform ever coupling to any one of their internals.
The only place agent-specific knowledge is allowed to live is the **adapter**.

## The `AgentAdapter` interface

```python
class AgentAdapter(ABC):
    """One implementation per integrated agent system."""

    def execute(
        self,
        case_input: dict,
        version_config: dict,
    ) -> AgentExecutionResult:
        """Invoke the target agent for one evaluation case and return a normalized result.

        MUST catch every exception raised by the target agent and return
        AgentExecutionResult(status="error", ...) instead of propagating it - the runner
        also enforces a timeout and a defensive try/except around this call, but the
        adapter is the layer that actually understands what a graceful vs. ungraceful
        failure looks like for its agent.
        """
```

`version_config` comes from `AgentVersion.config` - whatever the adapter needs to target a
specific version: a git ref to check out, an HTTP endpoint, a model name, feature flags.
The same adapter class serves every version of a given agent; only the config differs.

Adapters are registered by `Agent.adapter_key` in a simple in-process registry (a dict is
sufficient - no plugin framework needed at this scale):

```python
ADAPTER_REGISTRY: dict[str, type[AgentAdapter]] = {
    "incident-investigator": IncidentInvestigatorAdapter,
    # future: "rag-app": RagAppAdapter, "sql-agent": SqlAgentAdapter, ...
}
```

## The `AgentExecutionResult` contract

This is the single normalized shape every adapter must produce, regardless of what the
underlying agent looks like internally. It is the platform's only window into "what did the
agent do" - get this schema right and every evaluator, every trace viewer, and every future
adapter can be built against it without special cases.

```python
class ToolCallRecord(BaseModel):
    sequence_index: int
    tool_name: str
    arguments: dict
    result: dict | None
    status: Literal["success", "error"]
    latency_ms: float | None
    started_at: datetime | None

class TraceStep(BaseModel):
    step_type: Literal["reasoning", "message", "tool_call", "handoff", "other"]
    timestamp: datetime | None
    payload: dict  # shape varies by step_type; adapter-normalized, not agent-native

class TokenUsage(BaseModel):
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None

class ExecutionError(BaseModel):
    type: str
    message: str
    detail: dict | None = None

class AgentExecutionResult(BaseModel):
    status: Literal["success", "error", "timeout"]
    final_output: str | None          # primary human-readable output
    structured_output: dict | None    # if the agent produces structured data
    latency_ms: float
    token_usage: TokenUsage | None    # None if the agent genuinely can't report it - never fabricated
    cost_usd: float | None            # None if not computable - never fabricated
    tool_calls: list[ToolCallRecord]
    trace: list[TraceStep]            # normalized, ordered
    raw_output: dict                  # adapter's unprocessed response, kept for debugging / re-normalization
    error: ExecutionError | None      # set when status != "success"
```

Field-by-field rationale for what's included and why:

- **`final_output`** - every agent has *some* primary answer/response; this is the field
  deterministic and LLM-judge evaluators check first.
- **`structured_output`** - many agents (and definitely the Incident Investigation
  Platform) also produce structured data (e.g. `{root_cause, affected_hosts, confidence}`).
  Kept separate from `final_output` rather than requiring evaluators to parse it out of
  free text.
- **`status`** - distinguishes "the agent ran and gave an answer" from "the agent errored"
  from "the agent timed out," which is essential for run-level reporting (a case that
  errored is not the same failure mode as a case that ran and gave a wrong answer).
- **`latency_ms`** - always measurable by the adapter itself (wall-clock around the call),
  so this is never `None`; it doesn't depend on the target agent reporting anything.
- **`token_usage` / `cost_usd`** - optional and nullable because not every agent or
  provider exposes these, and the platform must never fabricate a number it can't
  substantiate. See `open-questions.md` for the unresolved question of whether cost should
  ever be derived platform-side from token usage and a pricing table.
- **`tool_calls`** - first-class and separate from `trace` because tool-selection and
  tool-efficiency evaluators need to query them directly (see `domain-model.md` on why
  `ToolCall` is its own table).
- **`trace`** - the full ordered sequence of steps (reasoning, messages, tool calls,
  agent-to-agent handoffs for multi-agent systems like the Incident Investigation
  Platform), normalized into a common envelope. The `payload` inside each step is
  intentionally loosely typed (`dict`) because step content genuinely varies by agent and
  step type - normalizing the *envelope* (type + order + timestamp) is what lets trace
  viewers and rule-based evaluators work generically; normalizing every possible payload
  shape up front would be premature.
- **`raw_output`** - the adapter's unprocessed response is always kept, even though it's
  redundant with the normalized fields, because normalization is lossy by construction and
  the raw response is what you need when debugging *why* normalization produced something
  unexpected, or when re-deriving a new normalized shape after the schema evolves.
- **`error`** - structured rather than a bare string, so error-type distributions can be
  queried across a run (e.g. "80% of failures in this run are timeouts against one
  downstream API").

## Adapter responsibilities

1. Translate `case_input` (whatever shape the dataset author chose) into the target
   agent's native invocation.
2. Invoke the agent - in-process import, HTTP call, subprocess, or CLI invocation,
   whichever fits how that agent is actually deployed. The platform does not prescribe a
   transport.
3. Measure latency around the call.
4. Catch every exception the agent raises and normalize it to
   `AgentExecutionResult(status="error", error=...)` - never let a raw exception escape
   `execute()`.
5. Map the agent's native trace / message history / tool-call log into `trace` and
   `tool_calls`. **This mapping logic is the single most agent-specific piece of code in
   the platform, and it lives entirely inside the adapter.**
6. Pass through `token_usage` and `cost_usd` only if the agent/provider actually reports
   them; otherwise leave `None`.

## Incident Investigation Platform adapter (first integration)

The target system is a multi-agent, LangGraph-based platform. Concretely, its adapter must:

- Invoke the platform (via whatever entry point it exposes - direct Python call if it's
  importable in-process, or HTTP if it runs as a service; this is an implementation detail
  decided when the adapter is built, not an architectural one).
- Translate LangGraph's internal state graph execution / message history into the
  `trace: list[TraceStep]` shape - e.g. each node transition or sub-agent handoff becomes a
  `TraceStep(step_type="handoff", ...)`, each tool invocation becomes both a `TraceStep`
  and a `ToolCallRecord`.
- This translation is the *only* place LangGraph is mentioned anywhere in this codebase.
  Nothing in `runner/`, `evaluators/`, the API, or the frontend has any LangGraph
  awareness - that is the whole point of the adapter boundary (ADR-0001).

## Adding a new agent later (e.g. a RAG app, a SQL agent)

1. Implement `AgentAdapter.execute()` for it, translating its native execution into
   `AgentExecutionResult`.
2. Register it in `ADAPTER_REGISTRY` under a new `adapter_key`.
3. Register an `Agent` row pointing at that key.
4. No change to the runner, evaluators, database schema, or frontend is required. If a
   change to any of those *is* required to onboard a new agent, that's a signal the
   `AgentExecutionResult` contract is missing something general - fix the contract, not
   the runner.
