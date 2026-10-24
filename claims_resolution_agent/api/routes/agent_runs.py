from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from claims_resolution_agent.application.services.agent_runs import AgentRunService
from claims_resolution_agent.domain.models import AgentRunData
from claims_resolution_agent.infrastructure.database import SessionLocal
from claims_resolution_agent.infrastructure.repositories.agent_runs import (
    AgentRunRepository,
)


router = APIRouter(
    prefix="/api/v1/agent-runs",
    tags=["agent-runs"],
)


def get_db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


def get_agent_run_service(
    session: Session = Depends(get_db),
) -> AgentRunService:
    repository = AgentRunRepository(session)
    return AgentRunService(repository)


@router.get(
    "/{run_id}",
    response_model=AgentRunData,
)
def get_agent_run(
    run_id: str,
    service: AgentRunService = Depends(get_agent_run_service),
) -> AgentRunData:
    agent_run = service.get_agent_run(run_id)

    if agent_run is None:
        raise HTTPException(
            status_code=404,
            detail=f"agent run not found: {run_id}",
        )

    return agent_run


@router.post(
    "",
    response_model=AgentRunData,
    status_code=201,
)
def create_agent_run(
    run_id: str,
    claim_id: str,
    service: AgentRunService = Depends(get_agent_run_service),
) -> AgentRunData:
    try:
        return service.create_agent_run(
            run_id=run_id,
            claim_id=claim_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{run_id}/status",
    response_model=AgentRunData,
)
def update_agent_run_status(
    run_id: str,
    status: str,
    error_message: str | None = None,
    service: AgentRunService = Depends(get_agent_run_service),
) -> AgentRunData:
    try:
        return service.update_status(
            run_id=run_id,
            status=status,
            error_message=error_message,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
