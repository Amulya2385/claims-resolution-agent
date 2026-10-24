from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from claims_resolution_agent.application.services.audit_events import (
    AuditEventService,
)
from claims_resolution_agent.domain.models import (
    AuditEventCreate,
    AuditEventData,
)
from claims_resolution_agent.infrastructure.database import SessionLocal
from claims_resolution_agent.infrastructure.repositories.audit_events import (
    AuditEventRepository,
)


router = APIRouter(
    prefix="/api/v1/audit-events",
    tags=["audit-events"],
)


def get_db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


def get_audit_event_service(
    session: Session = Depends(get_db),
) -> AuditEventService:
    repository = AuditEventRepository(session)
    return AuditEventService(repository)


@router.get(
    "/{event_id}",
    response_model=AuditEventData,
)
def get_audit_event(
    event_id: str,
    service: AuditEventService = Depends(get_audit_event_service),
) -> AuditEventData:
    event = service.get_event(event_id)

    if event is None:
        raise HTTPException(
            status_code=404,
            detail=f"audit event not found: {event_id}",
        )

    return event


@router.post(
    "",
    response_model=AuditEventData,
    status_code=201,
)
def create_audit_event(
    request: AuditEventCreate,
    service: AuditEventService = Depends(get_audit_event_service),
) -> AuditEventData:
    try:
        return service.create_event(
            event_id=request.event_id,
            claim_id=request.claim_id,
            run_id=request.run_id,
            event_type=request.event_type,
            actor_type=request.actor_type,
            actor_id=request.actor_id,
            payload=request.payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc