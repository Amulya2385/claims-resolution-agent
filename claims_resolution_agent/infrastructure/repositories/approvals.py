from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ApprovalRecord, ApprovalSignature


class ApprovalRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, approval_id: str) -> ApprovalRecord | None:
        statement = select(ApprovalRecord).where(
            ApprovalRecord.approval_id == approval_id
        )
        return self.session.scalar(statement)

    def add(self, approval: ApprovalRecord) -> ApprovalRecord:
        self.session.add(approval)
        self.session.flush()
        return approval

    def add_signature(
        self,
        signature: ApprovalSignature,
    ) -> ApprovalSignature:
        self.session.add(signature)
        self.session.flush()
        return signature

    def get_signatures(self, approval_id: str) -> list[ApprovalSignature]:
        statement = (
            select(ApprovalSignature)
            .where(ApprovalSignature.approval_id == approval_id)
            .order_by(ApprovalSignature.id)
        )
        return list(self.session.scalars(statement).all())

    def update_status(self, approval_id: str, status: str) -> ApprovalRecord:
        approval = self.get_by_id(approval_id)

        if approval is None:
            raise ValueError(f"approval not found: {approval_id}")

        approval.status = status
        self.session.flush()

        return approval