# 0009. LLM-judge client and credential strategy

Status: Accepted

## Context

The first LLM-as-judge evaluator (`grounding_judge`, docs/roadmap.md Phase 3) needs to
call a judge model. `docs/tech-stack.md` already commits to not adding heavyweight
frameworks or SDKs without a clear architectural need, and `httpx` is already a dependency
(used by `IncidentInvestigatorAdapter`). The environment this platform runs in already has
working Google Cloud Application Default Credentials (ADC) via the `gcloud` CLI, and the
target project already has Vertex AI enabled - reusing that is the path of least new
infrastructure.

## Decision

`GeminiJudgeClient` (`backend/app/evaluators/llm_judge/client.py`) calls Vertex AI's
`generateContent` REST endpoint directly via `httpx`, with `responseMimeType:
"application/json"` to get structured output without an SDK's help. For authentication,
it shells out to `gcloud auth application-default print-access-token` and caches the
resulting bearer token for ~45 minutes (under the real ~60 minute expiry), rather than
adding `google-auth` (or the much heavier `google-cloud-aiplatform`/Vertex AI SDK) as a
dependency to do the same token refresh in-process.

## Alternatives considered

- **Add the `google-auth` library** for in-process ADC token refresh, avoiding a
  subprocess call. This is the more conventional choice for anything beyond local
  development - see Consequences below - but was not taken for Phase 3 because the
  `gcloud` CLI was already a proven, working credential source in this environment
  (used throughout Phase 2's live verification) and adding a new dependency for exactly
  one token-refresh call, when a zero-dependency option already works, is the kind of
  addition `docs/tech-stack.md` asks to justify concretely rather than default into.
- **Add the full Vertex AI SDK** (`google-cloud-aiplatform` or `vertexai`). Rejected more
  strongly: it is a large dependency for what this platform needs (one JSON-in, JSON-out
  call), and the target Incident Investigation Platform already depends on it for its own
  agent logic - pulling the same SDK into the *evaluation* platform for an unrelated
  purpose blurs a line worth keeping clean (this platform depends on nothing that any
  specific integrated agent depends on).
- **A different judge provider** (e.g. an Anthropic or OpenAI model instead of Gemini).
  Not rejected on principle - the `GeminiJudgeClient` interface (`generate_json(prompt,
  temperature=...) -> dict`) is intentionally the only piece of `GroundingJudge` that
  would need to change to swap providers - but not built now because Vertex AI access was
  already verified working in this project's GCP setup, and adding a second provider
  integration without a concrete need would be speculative.

## Consequences

- Judge calls only work where the `gcloud` CLI is installed and already has valid
  Application Default Credentials - true for local development in this project today, but
  **not necessarily true of wherever this platform eventually runs in a more permanent
  deployment** (a minimal container image typically doesn't ship the `gcloud` CLI). This
  is a real, tracked limitation, not an oversight - see `docs/open-questions.md`. Revisit
  with `google-auth` (still no full SDK needed) before any deployment beyond a developer's
  own machine.

  **Confirmed live, not hypothetical, as of the Cloud Run deployment** ([ADR-0010](0010-cloud-run-deployment.md)):
  `grounding_judge` fails on the deployed service with exactly the predicted failure mode
  - `FileNotFoundError` on the `gcloud` subprocess call, isolated per-evaluator by the
  runner's existing failure isolation, the run otherwise completing normally. See
  `docs/phase-notes/deployment.md` for the exact reproduction. The `google-auth` swap
  named above is now a confirmed, not speculative, fix.
- `GeminiJudgeClient` is the only place that knows how Vertex AI auth or its REST shape
  works, mirroring how `AgentAdapter` implementations are the only places that know their
  target agent's specifics - a future second judge provider is a new class behind the same
  three-method interface, not a change to `GroundingJudge` or any other evaluator.
- The subprocess call adds real per-call latency the first time (or after the cache
  expires) - acceptable for evaluation runs, which are not latency-sensitive in the way a
  production request path would be.
