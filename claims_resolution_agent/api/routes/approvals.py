from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from claims_resolution_agent.application.services.approvals import ApprovalService
from claims_resolution_agent.domain.models import ApprovalData
from claims_resolution_agent.infrastructure.database import SessionLocal
from claims_resolution_agent.infrastructure.repositories.approvals import (
    ApprovalRepository,
)


router = APIRouter(
    prefix="/api/v1/approvals",
    tags=["approvals"],
)


class CreateApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str
    claim_id: str
    payload_hash: str
    required_approvers: int = Field(ge=0)
    expires_at: datetime


class SignApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approver_id: str


def get_db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


def get_approval_service(
    session: Session = Depends(get_db),
) -> ApprovalService:
    repository = ApprovalRepository(session)
    return ApprovalService(repository)


@router.get(
    "/{approval_id}",
    response_model=ApprovalData,
)
def get_approval(
    approval_id: str,
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalData:
    approval = service.get_approval(approval_id)

    if approval is None:
        raise HTTPException(
            status_code=404,
            detail=f"approval not found: {approval_id}",
        )

    return approval


@router.post(
    "",
    response_model=ApprovalData,
    status_code=201,
)
def create_approval(
    request: CreateApprovalRequest,
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalData:
    try:
        return service.create_approval(
            approval_id=request.approval_id,
            claim_id=request.claim_id,
            payload_hash=request.payload_hash,
            required_approvers=request.required_approvers,
            expires_at=request.expires_at,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.post(
    "/{approval_id}/signatures",
    response_model=ApprovalData,
)
def sign_approval(
    approval_id: str,
    request: SignApprovalRequest,
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalData:
    try:
        return service.add_signature(
            approval_id=approval_id,
            approver_id=request.approver_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc