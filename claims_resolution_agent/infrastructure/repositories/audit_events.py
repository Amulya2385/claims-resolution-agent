from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditEvent


class AuditEventRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, event_id: str) -> AuditEvent | None:
        statement = select(AuditEvent).where(
            AuditEvent.event_id == event_id
        )
        return self.session.scalar(statement)

    def get_by_claim_id(self, claim_id: str) -> list[AuditEvent]:
        statement = (
            select(AuditEvent)
            .where(AuditEvent.claim_id == claim_id)
            .order_by(AuditEvent.created_at.desc())
        )
        return list(self.session.scalars(statement).all())

    def get_by_run_id(self, run_id: str) -> list[AuditEvent]:
        statement = (
            select(AuditEvent)
            .where(AuditEvent.run_id == run_id)
            .order_by(AuditEvent.created_at.desc())
        )
        return list(self.session.scalars(statement).all())

    def add(self, event: AuditEvent) -> AuditEvent:
        self.session.add(event)
        self.session.flush()
        return event
