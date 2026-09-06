import enum


class EvaluatorType(str, enum.Enum):
    """docs/evaluation-architecture.md categories; runner treats all four uniformly."""

    DETERMINISTIC = "deterministic"
    RULE_BASED = "rule_based"
    LLM_JUDGE = "llm_judge"
    CUSTOM = "custom"


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class CaseRunStatus(str, enum.Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


class ToolCallStatus(str, enum.Enum):
    SUCCESS = "success"
    ERROR = "error"
