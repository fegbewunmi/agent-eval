# 0001. Agent-agnostic adapter architecture

Status: Accepted

## Context

The first system to evaluate is an Incident Investigation Platform built as a multi-agent
LangGraph application. It would be fastest, short-term, to build the evaluation platform's
core around LangGraph's execution model directly — reading its state graph, its message
format, its native trace representation. But the platform is explicitly required to later
evaluate structurally different systems (RAG apps, customer-support agents, coding agents,
SQL agents), which will not use LangGraph, may not even be graph-based, and may not be
Python-native processes at all (they could be remote HTTP services).

## Decision

Introduce a single seam — the `AgentAdapter` interface plus the `AgentExecutionResult`
normalized contract (`docs/agent-integration.md`) — between the evaluation platform and
every integrated agent. The runner, evaluators, database schema, API, and frontend only
ever interact with `AgentExecutionResult`. All agent-specific knowledge, including every
mention of LangGraph, is confined to the one adapter module for that agent
(`app/adapters/incident_investigator/`).

## Alternatives considered

- **Build the platform around LangGraph's execution/trace model directly.** Faster to
  build the first integration, but would require a rewrite of the runner and trace-viewing
  code the moment a non-LangGraph agent needs evaluating — defeats the platform's stated
  purpose.
- **A generic "agent must implement X interface" requirement placed on integrated agents
  themselves**, rather than an adapter the platform owns. Rejected because it would require
  modifying every target agent's own codebase to conform, which is often not feasible
  (the target agent may be owned by a different team, or may be a third-party system
  reachable only over HTTP) and reintroduces coupling in the other direction.

## Consequences

- Onboarding a new agent is "write one adapter file," not "extend the core platform" — the
  test of this (Phase 5 of `docs/roadmap.md`) is integrating at least two structurally
  different agents and confirming no core-code changes were needed beyond the
  `AgentExecutionResult` contract itself.
- The `AgentExecutionResult` schema becomes the platform's most important and hardest-to-
  change contract — see ADR-0006 for how its trace sub-schema is kept general without
  becoming vague.
- Adapters are the one place where non-platform dependencies (LangGraph, an HTTP client
  for a specific agent's API, etc.) are allowed to appear, and this needs to be enforced by
  convention/review, not by tooling, in the near term.
