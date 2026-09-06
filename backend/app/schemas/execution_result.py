"""The normalized adapter contract. docs/agent-integration.md.

Every AgentAdapter.execute(...) call returns an AgentExecutionResult, regardless of what
the underlying agent looks like internally. This is the one schema that keeps the runner,
evaluators, and (eventually) the frontend agent-agnostic (ADR-0001).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ToolCallRecord(BaseModel):
    sequence_index: int
    tool_name: str
    arguments: dict
    result: dict | None = None
    status: Literal["success", "error"]
    latency_ms: float | None = None
    started_at: datetime | None = None


class TraceStep(BaseModel):
    step_type: Literal["reasoning", "message", "tool_call", "handoff", "other"]
    timestamp: datetime | None = None
    payload: dict = {}


class TokenUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ExecutionError(BaseModel):
    type: str
    message: str
    detail: dict | None = None


class AgentExecutionResult(BaseModel):
    status: Literal["success", "error", "timeout"]
    final_output: str | None = None
    structured_output: dict | None = None
    latency_ms: float
    token_usage: TokenUsage | None = None
    cost_usd: float | None = None
    tool_calls: list[ToolCallRecord] = []
    trace: list[TraceStep] = []
    raw_output: dict = {}
    error: ExecutionError | None = None
