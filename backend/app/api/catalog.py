"""Read-only endpoints for browsing Agents/AgentVersions/Datasets/Evaluators.
docs/roadmap.md Phase 4: the frontend needs to list and select these; nothing here
creates/updates/deletes anything — registration still goes through
app/services/seed.py (agents/versions/evaluators) and scripts/load_dataset.py (datasets,
per ADR-0003's file-authoring decision), consistent with docs/phase-notes/phase-2.md's
explicit deferral of a full CRUD API until something concretely needs it.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.agent import Agent, AgentVersion
from app.models.dataset import Dataset, EvaluationCase
from app.models.evaluator import Evaluator
from app.schemas.api import (
    AgentSummary,
    AgentVersionSummary,
    DatasetCaseSummary,
    DatasetDetailResponse,
    DatasetSummary,
    EvaluatorSummary,
)

router = APIRouter(tags=["catalog"])


@router.get("/agents", response_model=list[AgentSummary])
def list_agents(session: Session = Depends(get_db)) -> list[AgentSummary]:
    agents = session.query(Agent).order_by(Agent.name).all()
    versions_by_agent: dict[uuid.UUID, list[AgentVersion]] = {}
    for version in session.query(AgentVersion).order_by(AgentVersion.created_at.desc()).all():
        versions_by_agent.setdefault(version.agent_id, []).append(version)

    return [
        AgentSummary(
            id=agent.id, name=agent.name, description=agent.description, adapter_key=agent.adapter_key,
            versions=[
                AgentVersionSummary(id=v.id, version_label=v.version_label, description=v.description, created_at=v.created_at)
                for v in versions_by_agent.get(agent.id, [])
            ],
        )
        for agent in agents
    ]


@router.get("/datasets", response_model=list[DatasetSummary])
def list_datasets(session: Session = Depends(get_db)) -> list[DatasetSummary]:
    datasets = session.query(Dataset).order_by(Dataset.name).all()
    return [
        DatasetSummary(
            id=d.id, name=d.name, description=d.description,
            case_count=session.query(EvaluationCase).filter_by(dataset_id=d.id).count(),
        )
        for d in datasets
    ]


@router.get("/datasets/{dataset_id}", response_model=DatasetDetailResponse)
def get_dataset(dataset_id: uuid.UUID, session: Session = Depends(get_db)) -> DatasetDetailResponse:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail=f"No Dataset with id={dataset_id}")
    cases = session.query(EvaluationCase).filter_by(dataset_id=dataset_id).order_by(EvaluationCase.key).all()
    return DatasetDetailResponse(
        id=dataset.id, name=dataset.name, description=dataset.description, case_count=len(cases),
        cases=[DatasetCaseSummary(id=c.id, key=c.key, tags=c.tags) for c in cases],
    )


@router.get("/evaluators", response_model=list[EvaluatorSummary])
def list_evaluators(session: Session = Depends(get_db)) -> list[EvaluatorSummary]:
    evaluators = session.query(Evaluator).order_by(Evaluator.key, Evaluator.version).all()
    return [
        EvaluatorSummary(
            id=e.id, key=e.key, version=e.version, type=e.type.value,
            dimension=e.dimension, description=e.description,
        )
        for e in evaluators
    ]
