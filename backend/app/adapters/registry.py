from app.adapters.base import AgentAdapter
from app.adapters.stub_agent.adapter import StubAgentAdapter

ADAPTER_REGISTRY: dict[str, type[AgentAdapter]] = {
    "stub-agent": StubAgentAdapter,
    # future: "incident-investigator": IncidentInvestigatorAdapter, per Phase 2
}


def get_adapter(adapter_key: str) -> AgentAdapter:
    try:
        adapter_cls = ADAPTER_REGISTRY[adapter_key]
    except KeyError as exc:
        raise ValueError(
            f"No adapter registered for adapter_key={adapter_key!r}. "
            f"Known adapters: {sorted(ADAPTER_REGISTRY)}"
        ) from exc
    return adapter_cls()
