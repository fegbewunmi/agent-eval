# 0006. Trace normalization schema

Status: Accepted

## Context

Different agents represent their execution history completely differently: a LangGraph
state machine's node transitions and message history, a simple ReAct loop's
thought/action/observation sequence, a RAG app's retrieve-then-generate steps. Rule-based
evaluators (tool selection, tool efficiency) and trace-viewing UI both need *some* common
structure to operate on generically — but over-specifying that structure would force every
future adapter's author to contort their agent's real execution into a shape it doesn't
naturally have.

## Decision

Normalize only the **envelope**, not the **content**, of each trace step:

```python
class TraceStep(BaseModel):
    step_type: Literal["reasoning", "message", "tool_call", "handoff", "other"]
    timestamp: datetime | None
    payload: dict   # shape varies by step_type and by agent; not schema-enforced further
```

`step_type` and ordering are normalized (every adapter must classify its steps into this
fixed small set of kinds and emit them in execution order) because that's what generic
rule-based evaluators and a trace-timeline UI actually need ("did a `handoff` happen before
a `tool_call`", "render a timeline in order"). `payload` is intentionally an open `dict` —
its content is adapter-specific and consumed either by humans reading the trace viewer or
by evaluators written with knowledge of a specific agent's payload shape (acceptable,
since such an evaluator is inherently agent-specific, unlike the generic rule-based
evaluators that only need `step_type`/order/`tool_calls`).

Tool calls are additionally promoted to a fully-typed `ToolCallRecord` (see
`docs/agent-integration.md`) and their own DB table (`ToolCall`, see `docs/domain-model.md`)
because they are common enough across nearly every agent type, and specific enough in
structure (name, arguments, result, status, timing), to be worth fully normalizing rather
than leaving as opaque payload.

## Alternatives considered

- **Fully normalize every step's payload into a fixed schema per `step_type`.** Rejected:
  would require anticipating every field every future agent's reasoning/message steps
  might need, which is exactly the premature generalization the design brief warns
  against; adapters would end up cramming agent-specific data into ill-fitting fixed
  fields or a catch-all "extra" field anyway.
- **No normalization at all — store each adapter's raw trace format and let evaluators
  and the UI special-case per agent.** Rejected: this defeats agent-agnosticism (ADR-0001)
  for exactly the components — rule-based evaluators and the trace UI — that most need to
  work generically across agents.
- **Normalize tool calls only as part of the trace payload, not as a separate typed
  record/table.** Considered, but rejected per the reasoning in `docs/domain-model.md`
  point 2: tool-selection and tool-efficiency evaluators need to query tool calls
  relationally, which a `payload` blob doesn't support without re-parsing per evaluator
  invocation.

## Consequences

- A new adapter author has a small, clear job for trace mapping: classify each of the
  agent's native execution steps into one of five `step_type`s, order them, and put
  whatever's useful for debugging into `payload`. Tool calls get the extra step of
  populating `ToolCallRecord` fields.
- Generic rule-based evaluators (tool selection, tool efficiency, "no forbidden tool
  after step N") can be written once against `tool_calls`/`step_type`/order and work for
  every adapter without modification — this is the concrete test of whether this ADR's
  balance point was right (Phase 5 of the roadmap, integrating additional adapters).
- Evaluators or UI features that need to interpret `payload` content are inherently
  agent-specific and should be written with that scoping made explicit (e.g. named/
  documented as "only meaningful for the Incident Investigation Platform's payload
  shape"), not treated as generic.
