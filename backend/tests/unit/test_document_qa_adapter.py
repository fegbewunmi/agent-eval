"""Unit tests for the Document Q&A adapter, against a mocked HTTP transport shaped like
the real /query response (verified by hand against a live instance - see
docs/phase-notes/phase-5.md). No live server/OpenAI calls here (docs/tech-stack.md).
"""

import httpx

from app.adapters.document_qa.adapter import DocumentQAAdapter, _extract_cited_claims

BASE_URL = "http://testserver"


def _chunk(text: str, score: float = 0.3) -> dict:
    return {"text": text, "score": score, "metadata": {"source": "document.pdf"}}


def _patch_client(monkeypatch, handler) -> None:
    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr("app.adapters.document_qa.adapter.httpx.Client", fake_client)


def test_grounded_answer_with_inline_marker_extracts_claim(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "question": "What GPA did the candidate achieve?",
            "chunks": [_chunk("...GPA of 4.0 at Texas A&M...")],
            "answer": "The candidate achieved a GPA of 4.0 [1].",
            "citedChunkIndices": [1],
            "answerable": True,
        })

    _patch_client(monkeypatch, handler)
    result = DocumentQAAdapter().execute({"question": "What GPA?"}, {"base_url": BASE_URL})

    assert result.status == "success"
    assert result.final_output == "The candidate achieved a GPA of 4.0 [1]."
    assert result.structured_output["answerable"] is True
    assert result.structured_output["supporting_evidence"] == ["The candidate achieved a GPA of 4.0 [1]."]
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "hybrid_retrieve"
    assert result.tool_calls[0].result["chunks"][0]["text"] == "...GPA of 4.0 at Texas A&M..."


def test_grounded_answer_without_inline_marker_falls_back_to_whole_answer(monkeypatch):
    """Real observed behavior (docs/phase-notes/phase-5.md): the model sometimes omits
    the [n] marker even though citedChunkIndices is correct. Grounding must still be
    checkable in this case, not silently n/a."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "question": "Where does the candidate work?",
            "chunks": [_chunk("Senior Software Engineer | Bloomberg LP")],
            "answer": "The candidate currently works for Bloomberg LP.",
            "citedChunkIndices": [1],
            "answerable": True,
        })

    _patch_client(monkeypatch, handler)
    result = DocumentQAAdapter().execute({"question": "Where?"}, {"base_url": BASE_URL})

    assert result.structured_output["supporting_evidence"] == ["The candidate currently works for Bloomberg LP."]


def test_refusal_has_no_supporting_evidence(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "question": "What is the capital of France?",
            "chunks": [],
            "answer": "I couldn't find any information related to this question in the indexed document.",
            "citedChunkIndices": [],
            "answerable": False,
        })

    _patch_client(monkeypatch, handler)
    result = DocumentQAAdapter().execute({"question": "?"}, {"base_url": BASE_URL})

    assert result.status == "success"  # a refusal is a successful execution, not an error
    assert result.structured_output["answerable"] is False
    assert "supporting_evidence" not in result.structured_output


def test_http_error_normalizes_to_status_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "Something went wrong"})

    _patch_client(monkeypatch, handler)
    result = DocumentQAAdapter().execute({"question": "?"}, {"base_url": BASE_URL})

    assert result.status == "error"
    assert result.error is not None


def test_extract_cited_claims_keeps_only_cited_sentences():
    answer = "This sentence has no citation. This one does [1]. So does this [2]."
    claims = _extract_cited_claims(answer, chunk_count=2)
    assert claims == ["This one does [1].", "So does this [2]."]


def test_extract_cited_claims_ignores_out_of_range_markers():
    answer = "This cites something that doesn't exist [9]."
    assert _extract_cited_claims(answer, chunk_count=2) == []


def test_extract_cited_claims_handles_adjacent_markers():
    """Observed live (docs/phase-notes/phase-5.md): the model sometimes cites multiple
    chunks for one sentence as adjacent markers, e.g. "...pgvector and Pinecone [1][2]."."""
    answer = "The candidate has experience with pgvector and Pinecone [1][2]."
    assert _extract_cited_claims(answer, chunk_count=2) == [answer]
