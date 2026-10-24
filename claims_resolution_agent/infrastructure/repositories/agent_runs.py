from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AgentRun


class AgentRunRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, run_id: str) -> AgentRun | None:
        statement = select(AgentRun).where(
            AgentRun.run_id == run_id
        )
        return self.session.scalar(statement)

    def get_by_claim_id(self, claim_id: str) -> list[AgentRun]:
        statement = (
            select(AgentRun)
            .where(AgentRun.claim_id == claim_id)
            .order_by(AgentRun.started_at.desc())
        )
        return list(self.session.scalars(statement).all())

    def add(self, agent_run: AgentRun) -> AgentRun:
        self.session.add(agent_run)
        self.session.flush()
        return agent_run
