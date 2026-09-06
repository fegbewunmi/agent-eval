"""Minimal client for Vertex AI's Gemini `generateContent` REST endpoint, used by
LLM-as-judge evaluators. docs/evaluation-architecture.md's required mitigations (a pinned
model version, temperature 0) are enforced here once, not left to each evaluator to
remember — every llm_judge evaluator should call through this client rather than hitting
the API directly.

Auth: shells out to `gcloud auth application-default print-access-token` and caches the
token for ~45 minutes, rather than adding a Google auth/Vertex AI SDK dependency for one
REST call. See ADR-0009 for the tradeoff (works cleanly for local dev; requires the gcloud
CLI to be installed and authenticated wherever this runs, which is a real constraint for
anything beyond local dev — tracked in docs/open-questions.md).
"""

import json
import subprocess
import time

import httpx

_TOKEN_TTL_SECONDS = 45 * 60  # refresh comfortably before the real ~60min expiry


class JudgeCallError(Exception):
    """The judge model call failed or returned something that couldn't be parsed as the
    expected JSON shape. Evaluators should catch this and let the runner's per-evaluator
    failure isolation (docs/architecture.md) handle it, same as any other evaluator error.
    """


class GeminiJudgeClient:
    def __init__(self, project_id: str, location: str = "us-central1", model: str = "gemini-2.5-flash"):
        self.project_id = project_id
        self.location = location
        self.model = model
        self._cached_token: str | None = None
        self._cached_at: float = 0.0

    def _access_token(self) -> str:
        if self._cached_token and (time.monotonic() - self._cached_at) < _TOKEN_TTL_SECONDS:
            return self._cached_token
        try:
            result = subprocess.run(
                ["gcloud", "auth", "application-default", "print-access-token"],
                capture_output=True, text=True, timeout=10, check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise JudgeCallError(f"could not obtain a Vertex AI access token: {exc}") from exc
        self._cached_token = result.stdout.strip()
        self._cached_at = time.monotonic()
        return self._cached_token

    def generate_json(self, prompt: str, *, temperature: float = 0.0) -> dict:
        """Calls the judge model with responseMimeType=application/json and returns the
        parsed JSON body. Raises JudgeCallError on any HTTP, network, or parse failure —
        never returns a partially-parsed or guessed result.
        """
        url = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/projects/"
            f"{self.project_id}/locations/{self.location}/publishers/google/"
            f"models/{self.model}:generateContent"
        )
        try:
            response = httpx.post(
                url,
                headers={"Authorization": f"Bearer {self._access_token()}"},
                json={
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
                },
                timeout=30.0,
            )
            response.raise_for_status()
            body = response.json()
            text = body["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except JudgeCallError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize every failure mode to one type
            raise JudgeCallError(f"judge call failed: {exc}") from exc
