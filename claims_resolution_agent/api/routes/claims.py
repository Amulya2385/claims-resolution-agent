from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from claims_resolution_agent.application.services.claims import ClaimService
from claims_resolution_agent.domain.models import ClaimData
from claims_resolution_agent.infrastructure.database import SessionLocal
from claims_resolution_agent.infrastructure.repositories.claims import ClaimRepository


router = APIRouter(
    prefix="/api/v1/claims",
    tags=["claims"],
)


def get_db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


def get_claim_service(
    session: Session = Depends(get_db),
) -> ClaimService:
    repository = ClaimRepository(session)
    return ClaimService(repository)


@router.get(
    "/{claim_id}",
    response_model=ClaimData,
)
def get_claim(
    claim_id: str,
    service: ClaimService = Depends(get_claim_service),
) -> ClaimData:
    claim = service.get_claim(claim_id)

    if claim is None:
        raise HTTPException(
            status_code=404,
            detail=f"claim not found: {claim_id}",
        )

    return claim


@router.post(
    "",
    response_model=ClaimData,
    status_code=201,
)
def create_claim(
    claim: ClaimData,
    service: ClaimService = Depends(get_claim_service),
) -> ClaimData:
    try:
        return service.create_claim(claim)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc