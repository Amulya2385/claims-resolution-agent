from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import RefundExecution


class RefundExecutionRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, execution: RefundExecution) -> RefundExecution:
        self.session.add(execution)
        self.session.flush()
        return execution

    def get_by_id(self, execution_id: int) -> RefundExecution | None:
        statement = select(RefundExecution).where(
            RefundExecution.id == execution_id
        )
        return self.session.scalar(statement)

    def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> RefundExecution | None:
        statement = select(RefundExecution).where(
            RefundExecution.idempotency_key == idempotency_key
        )
        return self.session.scalar(statement)

    def get_by_claim_id(
        self,
        claim_id: str,
    ) -> list[RefundExecution]:
        statement = (
            select(RefundExecution)
            .where(RefundExecution.claim_id == claim_id)
            .order_by(RefundExecution.id)
        )
        return list(self.session.scalars(statement).all())

    def update_status(
        self,
        execution_id: int,
        status: str,
    ) -> RefundExecution:
        execution = self.get_by_id(execution_id)

        if execution is None:
            raise ValueError(f"refund execution not found: {execution_id}")

        execution.status = status
        self.session.flush()

        return execution