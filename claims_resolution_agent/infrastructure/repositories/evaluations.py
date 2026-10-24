from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AgentRun, Evaluation


class EvaluationRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(
        self,
        evaluation_id: str,
    ) -> Evaluation | None:
        statement = select(Evaluation).where(
            Evaluation.evaluation_id == evaluation_id
        )

        return self.session.scalar(statement)

    def get_by_claim_id(
        self,
        claim_id: str,
    ) -> list[Evaluation]:
        statement = (
            select(Evaluation)
            .where(Evaluation.claim_id == claim_id)
            .order_by(Evaluation.created_at.desc())
        )

        return list(
            self.session.scalars(statement).all()
        )

    def get_by_run_id(
        self,
        run_id: str,
    ) -> list[Evaluation]:
        statement = (
            select(Evaluation)
            .where(Evaluation.run_id == run_id)
            .order_by(Evaluation.created_at.desc())
        )

        return list(
            self.session.scalars(statement).all()
        )

    def get_claim_id_for_run(
        self,
        run_id: str,
    ) -> str | None:
        statement = select(AgentRun.claim_id).where(
            AgentRun.run_id == run_id
        )

        return self.session.scalar(statement)

    def add(
        self,
        evaluation: Evaluation,
    ) -> Evaluation:
        self.session.add(evaluation)
        self.session.flush()

        return evaluation

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()