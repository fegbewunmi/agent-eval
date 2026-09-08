"""Grounding judge: is the agent's claimed supporting evidence actually backed by the
evidence it gathered, or fabricated? docs/evaluation-methodology.md "grounding".

This is the first LLM-as-judge evaluator (docs/roadmap.md Phase 3) - see
docs/evaluation-architecture.md for why grounding specifically needs judgment rather than
a rule: "is this claim supported by that evidence" requires reading natural language on
both sides, which a rule-based check can't do without an unbounded pile of special cases.

Unlike the deterministic/rule-based evaluators so far, this one needs no case-specific
`expected` configuration - it checks the agent's own claims against its own gathered
evidence (self-consistency), so it applies uniformly to any case where the agent produced
a `supporting_evidence` list and at least one tool call. Any adapter whose
AgentExecutionResult.structured_output includes a `supporting_evidence: list[str]` field
can use this evaluator, not just the incident investigator's.
"""

import json

from app.evaluators.base import Evaluator, EvaluatorResult
from app.evaluators.llm_judge.client import GeminiJudgeClient
from app.models.dataset import EvaluationCase
from app.schemas.execution_result import AgentExecutionResult

_PROMPT_TEMPLATE = """You are auditing an AI agent's incident-investigation reasoning for fabricated claims.

Evidence the agent actually gathered (tool call results - this is ground truth for this check):
{evidence}

Claims the agent listed as "supporting evidence" for its conclusion:
{claims}

For each claim, decide whether it is grounded (directly supported by the evidence above) \
or ungrounded (invented, not present in the evidence, or an unsupported extrapolation \
beyond what the evidence shows). Respond with ONLY a JSON object of this exact shape:
{{"ungrounded_claims": ["<claim text>", ...], "reasoning": "<one to three sentences explaining your judgement>"}}
If every claim is grounded, "ungrounded_claims" must be an empty list."""


class GroundingJudge(Evaluator):
    key = "grounding_judge"
    dimension = "grounding"

    def __init__(self, config: dict | None = None, client: GeminiJudgeClient | None = None) -> None:
        super().__init__(config)
        self._client = client  # lazily constructed in evaluate() if not injected (tests inject a fake)

    def _client_or_default(self) -> GeminiJudgeClient:
        if self._client is None:
            self._client = GeminiJudgeClient(
                project_id=self.config["project_id"],
                location=self.config.get("location", "us-central1"),
                model=self.config.get("model", "gemini-2.5-flash"),
            )
        return self._client

    def evaluate(
        self, case: EvaluationCase, execution_result: AgentExecutionResult
    ) -> list[EvaluatorResult]:
        claims = (execution_result.structured_output or {}).get("supporting_evidence")
        if not claims:
            return [
                EvaluatorResult(
                    dimension=self.dimension, score=0.0, passed=None,
                    reasoning="No supporting_evidence claims to check for this case run.",
                )
            ]

        evidence = [tool_call.result for tool_call in execution_result.tool_calls if tool_call.result]

        # A JudgeCallError here propagates to the runner, which isolates it per
        # (case_run, evaluator) exactly like any other evaluator failure
        # (docs/architecture.md) - never caught here to fabricate a pass/fail.
        judged = self._client_or_default().generate_json(
            _PROMPT_TEMPLATE.format(
                evidence=json.dumps(evidence, default=str),
                claims=json.dumps(claims),
            ),
            temperature=self.config.get("temperature", 0.0),
        )

        ungrounded = judged.get("ungrounded_claims", [])
        passed = len(ungrounded) == 0
        score = 1.0 if passed else max(0.0, 1.0 - len(ungrounded) / len(claims))

        return [
            EvaluatorResult(
                dimension=self.dimension,
                score=score,
                passed=passed,
                reasoning=judged.get("reasoning", ""),
                raw_output={"ungrounded_claims": ungrounded, "claims_checked": claims},
            )
        ]
