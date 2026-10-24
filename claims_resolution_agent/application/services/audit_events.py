import json
from datetime import datetime, timezone

from claims_resolution_agent.domain.models import AuditEventData
from claims_resolution_agent.infrastructure.models import AuditEvent
from claims_resolution_agent.infrastructure.repositories.audit_events import (
    AuditEventRepository,
)


class AuditEventService:
    def __init__(self, repository: AuditEventRepository):
        self.repository = repository

    def get_event(self, event_id: str) -> AuditEventData | None:
        event = self.repository.get_by_id(event_id)

        if event is None:
            return None

        return AuditEventData(
            event_id=event.event_id,
            claim_id=event.claim_id,
            run_id=event.run_id,
            event_type=event.event_type,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            payload=json.loads(event.payload),
            created_at=event.created_at,
        )

    def create_event(
        self,
        event_id: str,
        claim_id: str,
        run_id: str | None,
        event_type: str,
        actor_type: str,
        actor_id: str | None,
        payload: dict,
    ) -> AuditEventData:

        existing = self.repository.get_by_id(event_id)

        if existing is not None:
            raise ValueError(
                f"audit event already exists: {event_id}"
            )

        event = AuditEvent(
            event_id=event_id,
            claim_id=claim_id,
            run_id=run_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload=json.dumps(payload),
            created_at=datetime.now(timezone.utc),
        )

        self.repository.add(event)
        self.repository.session.commit()

        return self.get_event(event_id)
