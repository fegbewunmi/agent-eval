# stub-agent-smoke-v1

A 7-case smoke-test dataset for the stub agent adapter (`app/adapters/stub_agent`), used
to validate the platform's own correctness in Phase 1 before the real Incident
Investigation Platform adapter exists - see `docs/roadmap.md` Phase 1.

- Four cases cover each root-cause keyword the stub agent recognizes (disk, memory, cpu,
  network) - all expected to pass every deterministic evaluator on a correctly behaving
  agent version.
- One case (`ambiguous-alert-no-keyword-match`) has no matching keyword and expects
  `root_cause: unknown` - the stub agent's honest "I don't know" answer.
- Two cases exist purely to exercise failure isolation (docs/architecture.md "failure
  boundaries") and are excluded from any "how good is the agent" reading of results:
  - `simulated-agent-crash` sets `inject_failure: error`, which makes the adapter raise -
    proves one erroring case doesn't abort the run.
  - `simulated-wrong-answer` sets `inject_failure: wrong_answer`, which makes the agent
    return a wrong (but non-crashing) answer - proves the exact-match evaluator correctly
    catches a real regression rather than silently passing it.
