"""Small get-or-create helpers for registering Agents/AgentVersions/Evaluators.

Phase 1 has no CRUD API yet (that's Phase 2), so scripts/run_eval.py uses these directly
to make sure the rows a run needs exist before triggering it.
"""

from sqlalchemy.orm import Session

from app.models.agent import Agent, AgentVersion
from app.models.enums import EvaluatorType
from app.models.evaluator import Evaluator


def ensure_agent(session: Session, *, name: str, adapter_key: str, description: str | None = None) -> Agent:
    agent = session.query(Agent).filter_by(name=name).one_or_none()
    if agent is None:
        agent = Agent(name=name, adapter_key=adapter_key, description=description)
        session.add(agent)
        session.flush()
    return agent


def ensure_agent_version(
    session: Session, *, agent: Agent, version_label: str, config: dict | None = None,
    description: str | None = None,
) -> AgentVersion:
    """AgentVersion is immutable (docs/domain-model.md): if version_label already exists
    for this agent, the existing row is returned as-is and `config`/`description` are
    ignored - register a new version_label for a new config instead."""
    version = (
        session.query(AgentVersion)
        .filter_by(agent_id=agent.id, version_label=version_label)
        .one_or_none()
    )
    if version is None:
        version = AgentVersion(
            agent_id=agent.id,
            version_label=version_label,
            config=config or {},
            description=description,
        )
        session.add(version)
        session.flush()
    return version


def ensure_evaluator(
    session: Session, *, key: str, version: str, type: EvaluatorType, dimension: str,
    config: dict | None = None, description: str | None = None,
) -> Evaluator:
    """Mirrors AgentVersion immutability (ADR-0008): existing (key, version) rows are
    returned as-is."""
    evaluator = session.query(Evaluator).filter_by(key=key, version=version).one_or_none()
    if evaluator is None:
        evaluator = Evaluator(
            key=key, version=version, type=type, dimension=dimension,
            config=config or {}, description=description,
        )
        session.add(evaluator)
        session.flush()
    return evaluator
