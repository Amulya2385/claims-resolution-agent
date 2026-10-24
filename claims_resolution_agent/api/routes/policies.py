from fastapi import APIRouter, Depends, HTTPException, Query

from claims_resolution_agent.application.services.policies import PolicyService
from claims_resolution_agent.domain.models import PolicySearchResult


router = APIRouter(
    prefix="/api/v1/policies",
    tags=["policies"],
)


def get_policy_service() -> PolicyService:
    return PolicyService()


@router.get(
    "/search",
    response_model=list[PolicySearchResult],
)
def search_policy(
    query: str = Query(min_length=1),
    k: int = Query(default=4, ge=1, le=20),
    service: PolicyService = Depends(get_policy_service),
) -> list[PolicySearchResult]:
    try:
        return service.search_policy(query=query, k=k)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
