from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Decision


class DecisionRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, decision_id: str) -> Decision | None:
        statement = select(Decision).where(
            Decision.decision_id == decision_id
        )
        return self.session.scalar(statement)

    def get_by_run_id(self, run_id: str) -> list[Decision]:
        statement = (
            select(Decision)
            .where(Decision.run_id == run_id)
            .order_by(Decision.created_at.desc())
        )
        return list(self.session.scalars(statement).all())

    def get_by_claim_id(self, claim_id: str) -> list[Decision]:
        statement = (
            select(Decision)
            .where(Decision.claim_id == claim_id)
            .order_by(Decision.created_at.desc())
        )
        return list(self.session.scalars(statement).all())

    def add(self, decision: Decision) -> Decision:
        self.session.add(decision)
        self.session.flush()
        return decision
