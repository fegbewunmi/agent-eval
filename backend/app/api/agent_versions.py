"""The one write endpoint this API exposes for the Agent/AgentVersion
catalog - everything else in app/api/catalog.py stays deliberately
read-only (see that module's docstring and ADR-0003's original deferral of
a full CRUD API).

Real need this closes: agent-dev-platform ("Orion") publishes a real
AgentVersion with verified source provenance for an integrated agent
(its docs/adrs/0023-registry-not-deployment-platform.md,
docs/adrs/0024-ci-publishing-machine-identity.md) and needs a live,
callable evaluation target registered here for that exact publish - the
existing `AgentVersion.config.base_url` mechanism already supports this
(app/adapters/incident_investigator/adapter.py reads it directly), it was
just never reachable over HTTP; only app/services/seed.py could write it.

No new auth code: this service is deployed `--no-allow-unauthenticated`
(Cloud Run IAM protects the whole service, since - unlike agent-dev-
platform's API - nothing here ever needs to accept a human's JWT on the
same header). The same `roles/run.invoker` grant that already lets
agent-platform-api call POST /runs covers this endpoint too.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.agent import Agent
from app.services.seed import ensure_agent_version
from app.schemas.api import AgentVersionSummary

router = APIRouter(tags=["agent-versions"])


class CreateAgentVersionRequest(BaseModel):
    version_label: str
    config: dict = {}
    description: str | None = None


@router.post("/agents/{agent_id}/versions", response_model=AgentVersionSummary, status_code=201)
def create_agent_version(
    agent_id: uuid.UUID, body: CreateAgentVersionRequest, session: Session = Depends(get_db)
) -> AgentVersionSummary:
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"No Agent with id={agent_id}")

    version = ensure_agent_version(
        session, agent=agent, version_label=body.version_label, config=body.config, description=body.description
    )
    session.commit()

    return AgentVersionSummary(
        id=version.id, version_label=version.version_label, description=version.description,
        created_at=version.created_at,
    )
