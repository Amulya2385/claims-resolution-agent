from datetime import datetime, timezone

from claims_resolution_agent.domain.models import AgentRunData
from claims_resolution_agent.infrastructure.models import AgentRun
from claims_resolution_agent.infrastructure.repositories.agent_runs import (
    AgentRunRepository,
)


class AgentRunService:
    def __init__(self, repository: AgentRunRepository):
        self.repository = repository

    def get_agent_run(self, run_id: str) -> AgentRunData | None:
        agent_run = self.repository.get_by_id(run_id)

        if agent_run is None:
            return None

        return AgentRunData(
            run_id=agent_run.run_id,
            claim_id=agent_run.claim_id,
            status=agent_run.status,
            started_at=agent_run.started_at,
            completed_at=agent_run.completed_at,
            error_message=agent_run.error_message,
        )

    def create_agent_run(
        self,
        run_id: str,
        claim_id: str,
    ) -> AgentRunData:
        existing = self.repository.get_by_id(run_id)

        if existing is not None:
            raise ValueError(
                f"agent run already exists: {run_id}"
            )

        agent_run = AgentRun(
            run_id=run_id,
            claim_id=claim_id,
            status="started",
            started_at=datetime.now(timezone.utc),
        )

        self.repository.add(agent_run)
        self.repository.session.commit()

        return self.get_agent_run(run_id)

    def update_status(
        self,
        run_id: str,
        status: str,
        error_message: str | None = None,
    ) -> AgentRunData:
        agent_run = self.repository.get_by_id(run_id)

        if agent_run is None:
            raise ValueError(
                f"agent run not found: {run_id}"
            )

        agent_run.status = status
        agent_run.error_message = error_message

        if status in {"completed", "failed"}:
            agent_run.completed_at = datetime.now(timezone.utc)

        self.repository.session.commit()

        return self.get_agent_run(run_id)
