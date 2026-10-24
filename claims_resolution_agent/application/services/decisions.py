from datetime import datetime, timezone

from claims_resolution_agent.domain.models import DecisionData
from claims_resolution_agent.infrastructure.models import Decision
from claims_resolution_agent.infrastructure.repositories.decisions import (
    DecisionRepository,
)


class DecisionService:
    def __init__(self, repository: DecisionRepository):
        self.repository = repository

    def get_decision(self, decision_id: str) -> DecisionData | None:
        decision = self.repository.get_by_id(decision_id)

        if decision is None:
            return None

        return DecisionData(
            decision_id=decision.decision_id,
            run_id=decision.run_id,
            claim_id=decision.claim_id,
            tier=decision.tier,
            recommendation=decision.recommendation,
            reasons=decision.reasons.split("\n"),
            policy_clause=decision.policy_clause,
            status=decision.status,
            created_at=decision.created_at,
        )

    def create_decision(
        self,
        decision_id: str,
        run_id: str,
        claim_id: str,
        tier: str,
        recommendation: str,
        reasons: list[str],
        policy_clause: str,
        status: str,
    ) -> DecisionData:

        existing = self.repository.get_by_id(decision_id)

        if existing is not None:
            raise ValueError(
                f"decision already exists: {decision_id}"
            )

        decision = Decision(
            decision_id=decision_id,
            run_id=run_id,
            claim_id=claim_id,
            tier=tier,
            recommendation=recommendation,
            reasons="\n".join(reasons),
            policy_clause=policy_clause,
            status=status,
            created_at=datetime.now(timezone.utc),
        )

        self.repository.add(decision)
        self.repository.session.commit()

        return self.get_decision(decision_id)
