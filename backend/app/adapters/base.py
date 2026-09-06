"""AgentAdapter interface. docs/agent-integration.md, ADR-0001.

This is the only seam between the evaluation platform and a target agent. Nothing outside
an adapter module should need to know how the target agent is built.
"""

from abc import ABC, abstractmethod

from app.schemas.execution_result import AgentExecutionResult


class AgentAdapter(ABC):
    """One implementation per integrated agent system."""

    @abstractmethod
    def execute(self, case_input: dict, version_config: dict) -> AgentExecutionResult:
        """Invoke the target agent for one evaluation case and return a normalized result.

        MUST catch every exception raised by the target agent and return
        AgentExecutionResult(status="error", ...) instead of propagating it. The runner
        additionally wraps this call in its own try/except and timeout (docs/architecture.md
        "failure boundaries"), but the adapter is the layer that understands what a
        graceful vs. ungraceful failure looks like for its specific agent.
        """
        raise NotImplementedError
