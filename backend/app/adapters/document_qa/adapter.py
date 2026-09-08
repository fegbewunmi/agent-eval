"""Adapter for the Document Q&A RAG platform (github.com/fegbewunmi/document-qa).
docs/roadmap.md Phase 5 - the second real adapter, deliberately structurally different
from the Incident Investigation Platform (a single retrieve-then-synthesize call, not a
multi-agent investigation).

All Document-Q&A-specific knowledge (its /query contract, its citation-marker convention,
its answerable/refusal semantics) lives in this module, per ADR-0001.

Unlike IncidentInvestigatorAdapter, this is a single synchronous request/response call -
no polling, no background task. This required no change to the AgentAdapter interface:
execute() simply returns directly instead of polling, which is evidence the interface
doesn't secretly assume a long-running, poll-based agent shape (docs/phase-notes/phase-5.md).

case_input shape:
    {"question": "<natural language question>"}
version_config:
    {"base_url": "http://localhost:3001"}  # wherever the document-qa server runs
"""

import re
import time

import httpx

from app.adapters.base import AgentAdapter
from app.schemas.execution_result import (
    AgentExecutionResult,
    ExecutionError,
    ToolCallRecord,
    TraceStep,
)

_DEFAULT_BASE_URL = "http://localhost:3001"

# Mirrors document-qa's own deterministic claim extraction (that repo's ADR-010): split
# into sentences, keep only sentences carrying at least one valid [n] citation marker.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9]|$)")
_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")


def _extract_cited_claims(answer: str, chunk_count: int) -> list[str]:
    """Adapter-side translation of document-qa's citation convention into the generic
    "claims this agent asserts are evidence-backed" shape grounding_judge already expects
    (docs/evaluation-architecture.md) - not fabrication: it's the same technique that
    system's own faithfulness eval (server/lib/faithfulness.ts) already uses for the same
    purpose, ported to Python rather than duplicated as a second, subtly different
    heuristic invented here.
    """
    if not answer:
        return []
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(answer) if s.strip()]
    claims = []
    for sentence in sentences:
        markers = [int(m) for m in _CITATION_MARKER_RE.findall(sentence)]
        if any(1 <= m <= chunk_count for m in markers):
            claims.append(sentence)
    return claims


class DocumentQAAdapter(AgentAdapter):
    def execute(self, case_input: dict, version_config: dict) -> AgentExecutionResult:
        base_url = version_config.get("base_url", _DEFAULT_BASE_URL).rstrip("/")
        started = time.monotonic()

        try:
            with httpx.Client(base_url=base_url, timeout=60.0) as client:
                response = client.post("/query", json={"question": case_input["question"]})
                response.raise_for_status()
                body = response.json()
        except Exception as exc:  # noqa: BLE001 - adapter boundary must never propagate
            return AgentExecutionResult(
                status="error",
                latency_ms=(time.monotonic() - started) * 1000,
                raw_output={},
                error=ExecutionError(type=type(exc).__name__, message=str(exc)),
            )

        latency_ms = (time.monotonic() - started) * 1000
        answer = body.get("answer")
        answerable = bool(body.get("answerable", False))
        cited_indices = body.get("citedChunkIndices", [])
        chunks = body.get("chunks", [])

        structured_output = {
            "answerable": answerable,
            "citedChunkIndices": cited_indices,
            "chunks_retrieved": len(chunks),
        }
        # Only a genuine answer has claims worth ground-checking - a refusal has nothing
        # to verify grounding against (grounding_judge correctly reports "not applicable"
        # for these, per docs/evaluation-methodology.md's n/a convention).
        #
        # Observed against the real server (docs/phase-notes/phase-5.md): the synthesis
        # prompt asks the model to embed [n] markers in the answer text, but it doesn't
        # always comply even when citedChunkIndices is populated correctly - e.g. "The
        # candidate currently works for Bloomberg LP..." with citedChunkIndices=[1] but
        # no inline "[1]" anywhere in the text. Falling back to the whole answer as one
        # claim when no per-sentence markers are found keeps grounding checkable in that
        # case, rather than silently going "not applicable" purely because of a
        # formatting inconsistency unrelated to whether the answer is actually grounded.
        # This is not fabricated evidence - it's still the agent's own real answer text.
        if answerable and answer:
            claims = _extract_cited_claims(answer, len(chunks)) or [answer]
            structured_output["supporting_evidence"] = claims

        tool_calls = [
            ToolCallRecord(
                sequence_index=0,
                tool_name="hybrid_retrieve",
                arguments={"question": case_input["question"]},
                result={"chunks": chunks},
                status="success",
            )
        ]
        trace = [
            TraceStep(step_type="tool_call", payload={"tool": "hybrid_retrieve", "chunks_retrieved": len(chunks)}),
            TraceStep(step_type="message", payload={"answerable": answerable, "cited_chunk_indices": cited_indices}),
        ]

        return AgentExecutionResult(
            status="success",
            final_output=answer,
            structured_output=structured_output,
            latency_ms=latency_ms,
            token_usage=None,  # not exposed by /query - never fabricated (docs/agent-integration.md)
            cost_usd=None,
            tool_calls=tool_calls,
            trace=trace,
            raw_output=body,
        )
