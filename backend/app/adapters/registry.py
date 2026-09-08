from app.adapters.base import AgentAdapter
from app.adapters.document_qa.adapter import DocumentQAAdapter
from app.adapters.incident_investigator.adapter import IncidentInvestigatorAdapter
from app.adapters.stub_agent.adapter import StubAgentAdapter

ADAPTER_REGISTRY: dict[str, type[AgentAdapter]] = {
    "stub-agent": StubAgentAdapter,
    "incident-investigator": IncidentInvestigatorAdapter,
    "document-qa": DocumentQAAdapter,
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
