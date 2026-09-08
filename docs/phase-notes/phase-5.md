# Phase 5 notes - proving agent-agnosticism with Document Q&A

Status: complete. This phase was explicitly an architectural validation exercise, not a
features phase - the question was whether `AgentAdapter` -> `AgentExecutionResult` ->
runner -> evaluators -> persistence -> comparison -> frontend generalizes to a genuinely
different kind of agent, or whether it secretly assumes the Incident Investigation
Platform's shape.

**Headline result: the abstraction generalized completely unchanged.** No change was
needed to `AgentAdapter`, `AgentExecutionResult`, the runner, the persistence model, the
comparison service, or the frontend - not one line. The only additions were a new adapter
(expected and correct - that's the whole point of the interface) and two new
general-purpose deterministic evaluators, justified by a concrete gap the RAG integration
exposed. No ADR needed to change as a result - see "Why no ADR changed" below.

## What was built

- **`DocumentQAAdapter`** (`backend/app/adapters/document_qa/adapter.py`) for the real
  Document Q&A RAG platform (github.com/fegbewunmi/document-qa - React/TypeScript/
  Express/PostgreSQL+pgvector/OpenAI/LangChain). A single synchronous `POST /query` call -
  no polling, no background task, the opposite shape from the incident investigator's
  fire-and-poll pattern. Maps retrieval (hybrid vector + full-text search, RRF fusion, LLM
  reranking - all internal to that system) onto one `ToolCallRecord` named
  `hybrid_retrieve`, and the synthesized answer/citations/refusal state onto
  `structured_output`. `token_usage`/`cost_usd` are honestly `None` - `/query` doesn't
  expose them, and nothing was fabricated to fill the fields in.
- **A citation-marker claim extractor** (`_extract_cited_claims`) that mirrors that
  project's own deterministic claim-extraction convention (its `ADR-010`): split the
  answer into sentences, keep only sentences carrying a valid `[n]` marker. This is
  adapter-side translation of a Document-Q&A-specific convention into the generic "claims
  this agent asserts are evidence-backed" shape `grounding_judge` already expects - not
  fabrication, since it reuses the exact technique that system's own faithfulness eval
  already applies for the same purpose, ported to Python rather than duplicated as a
  second, subtly different heuristic.
- **Two new deterministic evaluators**
  (`backend/app/evaluators/deterministic/text_contains.py`): `final_output_contains_keywords`
  (dimension `task_correctness`) and `retrieved_text_contains_keywords` (dimension
  `retrieval`, a new dimension). Justified concretely: the existing deterministic
  evaluators only handle exact-match or numeric-threshold checks on *structured* fields;
  neither can express "does this synthesized free-text answer mention the expected
  facts," which a RAG system's answer genuinely needs. Both are general-purpose in
  mechanism (substring containment over `final_output` / over any tool call's textual
  results), not RAG-specific - either could serve the incident investigator's
  `investigation_summary` too, unused there so far only because its structured categorical
  fields already cover what's needed.
- **A real 7-case dataset** (`datasets/document-qa/resume-v1/`) - see "The missing test
  fixture" below for why it's a resume PDF and not the "Widget X200" corpus that system's
  own design doc describes.
- **13 new tests** (7 for the adapter against a mocked HTTP transport, 6 for the two new
  evaluators), 57 total, all passing, none making live calls.

## How Document Q&A differs structurally from Incident Investigator

| | Incident Investigator | Document Q&A |
|---|---|---|
| Shape | Multi-agent LangGraph investigation | Single retrieve-then-synthesize call |
| Invocation | `POST` returns 202, poll `GET .../status` | `POST /query` returns the full result directly |
| "Tool calls" | Three specialist sub-agents (telemetry/deployment/knowledge), each invoked 0-N times by a planner | One retrieval action (`hybrid_retrieve`), always exactly once |
| Structured output | Ranked hypotheses with category/service/confidence | An answer, citation indices, an `answerable` flag |
| Grounding evidence | Tool call results (metrics, deployments, docs) | The same shape - retrieved chunks - despite being a completely different domain |
| Real LLM calls per case | ~9 (planner loop, analysis, synthesis) | 2 (rerank, synthesis) - or 1 if a static refusal threshold trips before any LLM call |
| Failure/refusal semantics | `escalated` phase, still "successful" execution | `answerable: false`, still "successful" execution - same design principle, arrived at independently by that project |

## Assumptions the second integration exposed - and how each was resolved

1. **Does the interface assume a long-running, poll-based agent?** No.
   `AgentAdapter.execute()` just has to return an `AgentExecutionResult`; nothing about the
   interface cares whether that happens after one fast HTTP call or after minutes of
   polling. `DocumentQAAdapter.execute()` is a fifth of the length of
   `IncidentInvestigatorAdapter.execute()` specifically because it doesn't need a polling
   loop - it needed less code, not different code.
2. **Does `grounding_judge` assume a pre-decomposed list of claim strings?** Its
   `structured_output.get("supporting_evidence")` contract is genuinely generic (any list
   of claim strings), but the *incident investigator* happens to already produce that list
   itself (`Hypothesis.supporting_evidence`), while Document Q&A produces one prose answer
   with inline markers. This is not an evaluator-interface gap - it's exactly the kind of
   translation work an adapter exists to do. Resolved entirely inside
   `DocumentQAAdapter` via `_extract_cited_claims`; `grounding_judge` itself needed zero
   changes and doesn't know which agent produced the list it's checking.
3. **Does `required_tool_calls`/`no_redundant_tool_calls` assume a multi-tool agent?** No
   code change was needed, but the *value* of these two evaluators is genuinely different
   for a single-tool agent: `required_tool_calls` has nothing meaningful to assert (there's
   only one tool, always called) so every Document Q&A case simply leaves `required_tools`
   unconfigured and it reports "not applicable" - exactly the n/a semantics
   `docs/evaluation-methodology.md` describes, working as designed. `no_redundant_tool_calls`
   still applies and still passes, just less interestingly (a single-tool agent will always
   pass it). Documented here rather than silently included as if it were equally
   informative for both agents.
4. **Does the persistence model (JSONB `structured_output`/`normalized_trace`) assume any
   particular field names?** No - confirmed by writing and reading back real Document Q&A
   data with completely different field names (`answerable`, `citedChunkIndices`,
   `chunks_retrieved`) than the incident investigator's (`root_cause_category`,
   `confidence_pct`, ...) with no schema or query changes.
5. **Does the frontend assume incident-investigator-specific field names anywhere?** No -
   confirmed live: every page (run summary, case inspector, agent list) rendered real
   Document Q&A data correctly with zero frontend code changes, because
   `CaseRunDetailResponse.structured_output` is rendered as a generic JSON block and
   `tool_calls`/`normalized_trace` are rendered by iterating generically, never by naming a
   specific expected field.

## Why no ADR changed

Every ADR (0001 agent-agnostic adapter architecture, 0002 evaluator type separation, 0003
dataset representation, 0004 immutable runs, 0005 synchronous execution, 0006 trace
normalization, 0007 deterministic-vs-judge sequencing, 0008 evaluator versioning, 0009
judge credentials) held up unchanged - none of their decisions needed revisiting, and none
of their consequences were contradicted by this integration. Adding two new evaluator
*implementations* is populating ADR-0002's existing `deterministic` category, the same
kind of change Phase 2 and Phase 3 already made repeatedly - not a new decision. Per the
brief for this phase, ADR-0005 in particular was left alone: this phase produced no
evidence synchronous execution is inadequate (Document Q&A's real queries took 2-3 seconds
each, far under any timeout), so it wasn't touched.

## Evaluation dimensions: what applied and what legitimately didn't

Ran the *entire* existing evaluator set unchanged against Document Q&A (the same
`ALL_EVALUATORS` list `scripts/run_eval.py` already used for every other agent) rather than
hand-picking a Document-Q&A-flavored subset, specifically to let non-applicable dimensions
demonstrate n/a correctly:

| Dimension | Applied? | Result |
|---|---|---|
| `completion` | Yes, unchanged | 1.00 (7/7) |
| `task_correctness` | Yes - `structured_field_exact_match` (`answerable`) + the new `final_output_contains_keywords` | 1.00 (12 results, 9 n/a from `structured_field_minimum` having nothing to check) |
| `latency` | Yes, unchanged | 1.00 (7/7, real latencies 2.0-3.1s) |
| `grounding` | Yes, unchanged (`grounding_judge`) | 1.00 (5/5 applicable; correctly n/a on both refusal cases, which have nothing to ground-check) |
| `retrieval` | Yes - the new `retrieved_text_contains_keywords` | 1.00 (1/1 configured case; correctly n/a on the other 6, which didn't need retrieval content asserted) |
| `tool_efficiency` | Yes, unchanged (`no_redundant_tool_calls`) | 1.00 (7/7) - trivially true for a single-tool agent, and reported as such, not treated as a meaningful signal |
| `tool_selection` | **Legitimately n/a for every case** (`required_tool_calls`) | n/a (0/7) - deliberately left unconfigured; a single-tool agent has nothing for this evaluator to assert |

`tool_selection` reporting entirely n/a, by design, is exactly the validation point
Definition of Done item 3 asks for.

## Bugs and real findings discovered along the way

1. **The dataset the design doc describes doesn't exist.** Document Q&A's own
   `docs/DESIGN-DOC.md` documents a labeled test set (Q-001 through Q-007) built against a
   "Widget X200 Maintenance Guide" PDF with specific ground truth (an error code, a SKU,
   warranty terms) - but that PDF was never committed to the repo and isn't present
   anywhere on disk (confirmed by searching the whole home directory). Resolved by using a
   real resume PDF instead (with the user's explicit sign-off), deriving all `expected`
   values directly from its actual text before running any query - see
   `datasets/document-qa/resume-v1/README.md`.
2. **A stray, six-day-old `next-server` process (the `ai-operations` frontend, long
   abandoned) was squatting on port 3001**, silently absorbing the doc-qa server's first
   startup attempt (which printed "Server running" and then died with an unlogged
   `EADDRINUSE`). Killed (stateless, safe) and the real server started cleanly.
3. **The Document Q&A model doesn't reliably include inline `[n]` citation markers even
   when `citedChunkIndices` is populated correctly** - observed directly:
   `"The candidate currently works for Bloomberg LP."` with `citedChunkIndices: [1]` but no
   `[1]` anywhere in the text, immediately followed by a different question that *did*
   get an inline marker. This isn't a platform bug, but the adapter has to account for it:
   falls back to treating the whole answer as one groundable claim when no per-sentence
   markers are found, so `grounding_judge` stays meaningful rather than going spuriously
   n/a on real, genuine answers. Documented and pinned down with a test
   (`test_grounded_answer_without_inline_marker_falls_back_to_whole_answer`).
4. **The local Cloud SQL proxy tunnel to `ai-ops-db` degraded again mid-phase** (same
   environmental fragility as Phase 4 - see that phase's notes), causing the
   incident-investigator regression re-check to briefly 500 with
   `psycopg.OperationalError: the connection is closed`. Restarting the AI Ops backend
   (the proxy process itself was still alive this time, just holding stale pooled
   connections) fixed it. Called out explicitly as environmental, not a Phase 5 code
   regression - see "Re-verifying the Incident Investigator integration" below.

## Live verification

**Document Q&A, full pipeline, real server, real OpenAI calls:** all 7 cases in
`document-qa-resume-v1` run through `scripts/run_eval.py` with every evaluator including
`grounding_judge` (real Vertex AI Gemini calls, independent of Document Q&A's own OpenAI
stack). Every dimension scored 1.00 where applicable; `tool_selection` correctly reported
entirely n/a. Spot-checked one case's full stored detail via the API
(`GET /runs/{id}/cases/{case_run_id}`) against what was actually asked/returned - accurate.
Confirmed visible and rendering correctly in the frontend (run summary, tag chips
including the new dataset's tags, case inspector) with zero frontend code changes - a
screenshot-verified pass, not just an HTTP 200 check.

**Re-verifying the Incident Investigator integration:** re-ran
`incident-investigator-smoke-v1` (all 3 real fixtures, all evaluators) after the Cloud SQL
proxy hiccup above was resolved. Result: `INC-FD-001` completed cleanly (all dimensions
passing, including grounding). `INC-LR-001` completed and was genuinely, correctly flagged
by `grounding_judge` for a real discrepancy (the synthesized answer said latency climbed
"over 40 minutes" against evidence showing 25 minutes, and mischaracterized a slight CPU/
memory increase as "stable or decreasing") - a legitimate judge finding, not a platform
bug, and further evidence the judge is discriminating rather than rubber-stamping.
`INC-RL-001` hit a transient `Connection reset by peer` mid-investigation - the runner's
failure isolation handled it exactly as designed (the run completed with the other two
cases' real results intact, the failed case recorded as `error` with a normalized
`ExecutionError` rather than crashing the run). No adapter, runner, or evaluator code was
touched for the incident investigator in this phase, and nothing about this run's failure
mode is new or different from failure modes already documented in Phases 2-4 - concluded
this is environmental (the same local Cloud SQL proxy fragility already seen twice before),
not a regression.

## Decisions and tradeoffs

- **Used the user's resume as the test corpus** rather than reconstructing the missing
  "Widget X200" fixture, per explicit sign-off - the more rigorous choice (real content,
  zero fabricated ground truth) at the cost of an unusual-looking corpus for a technical
  eval dataset.
- **Single-claim fallback for missing citation markers** in the adapter (see Bugs #3) -
  chosen over either (a) leaving grounding n/a whenever the model skips inline markers
  (loses real signal for no good reason) or (b) inventing sentence-level claims the model
  never actually asserted (fabrication). The fallback uses only the agent's own real
  answer text either way.
- **Two new evaluators, not a generic field-resolution mini-language.** A tempting
  alternative was one configurable evaluator that could check substrings against an
  arbitrary named field via a small DSL (`{"field": "any.nested.path"}`); rejected as
  exactly the kind of speculative abstraction this phase was told not to build - two small,
  explicitly-named evaluators (`final_output_contains_keywords`,
  `retrieved_text_contains_keywords`) cover the concrete need without inventing a query
  language nothing else needs yet.
- **Ran the full existing evaluator set rather than a hand-picked Document-Q&A subset** -
  specifically so non-applicable dimensions would demonstrate n/a semantics for real,
  rather than curating them away and only ever showing evaluators in their best light.

## Final test count

**57 backend tests, all passing** (44 going into this phase + 13 new: 7 adapter tests, 6
evaluator tests). No live calls in the automated suite; live verification was done
separately and is documented above.

## Definition of done - status

1. Document Q&A integrated as a second real `AgentAdapter`. **Done.**
2. Runs through the same core evaluation pipeline, unmodified. **Done** - zero core
   changes.
3. Applicable evaluators produce trustworthy results; non-applicable dimensions remain
   n/a. **Done** - `tool_selection` at 0/7 applicable is the clearest demonstration.
4. Any abstraction weakness is fixed generically, not patched into the Document Q&A
   adapter. **N/A in the strongest sense** - no abstraction weakness was found. Two new
   evaluators were added because of a concrete, general gap (free-text substring
   checking), not to patch around a weakness.
5. The existing Incident Investigator integration still works. **Done**, re-verified live
   (see above); the one failure encountered was environmental and handled correctly by
   existing failure-isolation design, not a regression.
6. Full automated test suite passes. **Done** - 57/57.
7. At least one real end-to-end Document Q&A run completed and inspected. **Done** - full
   7-case run, spot-checked via the API and the frontend (screenshots).
8. Findings and architectural implications documented. **This document.**
9. Roadmap marks Phase 5 complete. **Done** - see `docs/roadmap.md`.

Per the brief, this is the last phase - no Phase 6 is planned. This document set now
covers a validated, agent-agnostic Agent Evaluation Platform through two real, structurally
different integrations.
