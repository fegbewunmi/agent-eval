# Assumptions and Open Questions

Recorded explicitly, per the design brief's instruction to document assumptions rather
than silently resolve them. Each item below should be revisited when it starts to matter
in practice, not before.

## Assumptions made

- The Incident Investigation Platform is invokable in a way that can be wrapped by an
  in-process or HTTP adapter within a reasonable timeout (seconds to low minutes per case).
  If it requires long-running async workflows (hours), the synchronous execution model in
  ADR-0005 needs revisiting sooner than Phase 5.
- Evaluation cases are single-shot: one input produces one complete agent execution to
  evaluate. Multi-turn conversational evaluation (a case that is itself a sequence of
  turns) is not assumed in the MVP data model. See "Open questions" below.
- A single static API key is sufficient authentication for the lifetime of this being an
  internal tool used by one team.
- "Agent" in this platform means "a thing that takes a structured input and produces an
  output plus a trace" — broad enough to cover RAG apps, SQL agents, and multi-agent
  systems alike, without further generalization being needed.

## Open questions

1. **Dataset versioning.** `Dataset`/`EvaluationCase` are mutable in the current model,
   with only a content hash (`EvaluationRun.dataset_snapshot_hash`) to detect drift after
   the fact (ADR-0003). Is detection-after-the-fact good enough, or will teams need true
   point-in-time dataset snapshots (e.g. to reproduce a run from six months ago exactly)?
   Revisit if drift-related confusion actually occurs.

2. **Cost computation source of truth.** Should `CaseRun.cost_usd` ever be *computed* by
   the platform from `token_usage` plus a maintained model-pricing table, for agents that
   report tokens but not dollar cost — or should the platform only ever display cost that
   the adapter/agent itself reports, treating anything else as out of scope? Computing it
   platform-side adds a pricing-table maintenance burden; not computing it means cost data
   is inconsistently available across agents.

3. **Non-deterministic agents / multiple trials per case.** Many agents (especially
   LLM-based ones) are not deterministic even at temperature 0 in practice. Should the
   runner support running a case N times and reporting a distribution, rather than a single
   `CaseRun`? Not in the MVP data model (`EvaluationRun` → one `CaseRun` per case), but the
   schema doesn't prevent adding a `trial_index` to `CaseRun` later if this becomes
   necessary.

4. **Multi-turn / conversational evaluation cases.** The current model assumes one input →
   one execution. If a future integrated agent (e.g. a customer-support agent) needs to be
   evaluated over a multi-turn conversation, does `EvaluationCase.input` just become
   "a list of turns" (no schema change, since `input` is JSONB), or does this need a
   first-class `turn` concept in the domain model? Leaning toward the former until a
   concrete multi-turn evaluator need shows the latter is required.

5. **Human annotation / gold-label workflow.** The data model doesn't preclude a human
   reviewing and correcting `EvaluationCase.expected` or overriding an `EvaluationResult`,
   but no workflow or UI for this exists yet. Worth designing once LLM-as-judge (Phase 3)
   creates a concrete need to calibrate against human judgment.

6. **Statistical rigor for regression claims.** `evaluation-methodology.md` currently
   relies on raw case-level regression lists rather than confidence intervals or
   significance tests. Is this sufficient given expected dataset sizes (tens of cases), or
   will teams want formal statistical treatment once datasets grow into the hundreds?

7. **Evaluator config change vs. evaluator version bump — how strict?** ADR-0008 says
   "bump the version whenever config/prompt/logic changes meaningfully," which leaves
   "meaningfully" as a judgment call. Should this be enforced (e.g. hash the config and
   auto-suffix the version) rather than left to developer discipline? Leaning toward
   auto-hashing as a safety net once evaluator configs start changing frequently in
   practice — not needed while there are only a handful of hand-maintained evaluators.

8. **Where does the line sit between "adapter" and "target agent deployment"?** E.g. if the
   Incident Investigation Platform needs to be spun up (containers, dependent services) to
   be evaluated at all, is standing that up the adapter's job, a documented prerequisite
   the operator handles before running evaluations, or something in between? Decide when
   building the real adapter in Phase 2 — likely "documented prerequisite," to keep the
   adapter itself simple, but not yet confirmed.
