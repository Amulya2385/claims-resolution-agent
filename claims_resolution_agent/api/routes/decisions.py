from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from claims_resolution_agent.application.services.decisions import DecisionService
from claims_resolution_agent.domain.models import DecisionData
from claims_resolution_agent.infrastructure.database import SessionLocal
from claims_resolution_agent.infrastructure.repositories.decisions import (
    DecisionRepository,
)


router = APIRouter(
    prefix="/api/v1/decisions",
    tags=["decisions"],
)


class DecisionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    run_id: str
    claim_id: str
    tier: str
    recommendation: str
    reasons: list[str]
    policy_clause: str
    status: str


def get_db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


def get_decision_service(
    session: Session = Depends(get_db),
) -> DecisionService:
    repository = DecisionRepository(session)
    return DecisionService(repository)


@router.get(
    "/{decision_id}",
    response_model=DecisionData,
)
def get_decision(
    decision_id: str,
    service: DecisionService = Depends(get_decision_service),
) -> DecisionData:
    decision = service.get_decision(decision_id)

    if decision is None:
        raise HTTPException(
            status_code=404,
            detail=f"decision not found: {decision_id}",
        )

    return decision


@router.post(
    "",
    response_model=DecisionData,
    status_code=201,
)
def create_decision(
    request: DecisionCreateRequest,
    service: DecisionService = Depends(get_decision_service),
) -> DecisionData:
    try:
        return service.create_decision(
            decision_id=request.decision_id,
            run_id=request.run_id,
            claim_id=request.claim_id,
            tier=request.tier,
            recommendation=request.recommendation,
            reasons=request.reasons,
            policy_clause=request.policy_clause,
            status=request.status,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc