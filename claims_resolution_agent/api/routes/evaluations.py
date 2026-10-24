from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from claims_resolution_agent.application.services.evaluations import (
    EvaluationService,
)
from claims_resolution_agent.domain.models import (
    EvaluationCreate,
    EvaluationData,
)
from claims_resolution_agent.infrastructure.database import SessionLocal
from claims_resolution_agent.infrastructure.repositories.evaluations import (
    EvaluationRepository,
)


router = APIRouter(
    prefix="/api/v1/evaluations",
    tags=["evaluations"],
)


def get_db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


def get_evaluation_service(
    session: Session = Depends(get_db),
) -> EvaluationService:
    repository = EvaluationRepository(session)
    return EvaluationService(repository)


@router.get(
    "/{evaluation_id}",
    response_model=EvaluationData,
)
def get_evaluation(
    evaluation_id: str,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationData:
    evaluation = service.get_evaluation(evaluation_id)

    if evaluation is None:
        raise HTTPException(
            status_code=404,
            detail=f"evaluation not found: {evaluation_id}",
        )

    return evaluation


@router.post(
    "",
    response_model=EvaluationData,
    status_code=201,
)
def create_evaluation(
    evaluation: EvaluationCreate,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationData:
    try:
        return service.create_evaluation(evaluation)

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc