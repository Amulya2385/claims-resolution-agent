from datetime import datetime, timezone

from claims_resolution_agent.domain.models import (
    ApprovalData,
    ApprovalSignatureData,
)
from claims_resolution_agent.infrastructure.models import (
    ApprovalRecord,
    ApprovalSignature,
)
from claims_resolution_agent.infrastructure.repositories.approvals import (
    ApprovalRepository,
)


class ApprovalService:
    def __init__(self, repository: ApprovalRepository):
        self.repository = repository

    def get_approval(self, approval_id: str) -> ApprovalData | None:
        approval = self.repository.get_by_id(approval_id)

        if approval is None:
            return None

        signatures = self.repository.get_signatures(approval_id)

        return ApprovalData(
            approval_id=approval.approval_id,
            claim_id=approval.claim_id,
            payload_hash=approval.payload_hash,
            required_approvers=approval.required_approvers,
            signatures=[
                ApprovalSignatureData(
                    approver_id=signature.approver_id,
                    signed_at=signature.signed_at,
                )
                for signature in signatures
            ],
            created_at=approval.created_at,
            expires_at=approval.expires_at,
            status=approval.status,
        )

    def create_approval(
        self,
        approval_id: str,
        claim_id: str,
        payload_hash: str,
        required_approvers: int,
        expires_at: datetime,
    ) -> ApprovalData:
        existing = self.repository.get_by_id(approval_id)

        if existing is not None:
            raise ValueError(f"approval already exists: {approval_id}")

        approval = ApprovalRecord(
            approval_id=approval_id,
            claim_id=claim_id,
            payload_hash=payload_hash,
            required_approvers=required_approvers,
            status="pending",
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        )

        self.repository.add(approval)
        self.repository.session.commit()

        return self.get_approval(approval_id)

    def add_signature(
        self,
        approval_id: str,
        approver_id: str,
    ) -> ApprovalData:
        approval = self.repository.get_by_id(approval_id)

        if approval is None:
            raise ValueError(f"approval not found: {approval_id}")

        if approval.status != "pending":
            raise ValueError(
                f"approval {approval_id} is not pending"
            )

        existing_signatures = self.repository.get_signatures(approval_id)

        if any(
            signature.approver_id == approver_id
            for signature in existing_signatures
        ):
            raise ValueError(
                f"{approver_id} has already signed this approval"
            )

        if len(existing_signatures) >= approval.required_approvers:
            raise ValueError(
                f"approval {approval_id} already has enough signatures"
            )

        if datetime.now(timezone.utc) > approval.expires_at:
            approval.status = "expired"
            self.repository.session.commit()
            raise ValueError(f"approval {approval_id} expired")

        signature = ApprovalSignature(
            approval_id=approval_id,
            approver_id=approver_id,
            signed_at=datetime.now(timezone.utc),
        )

        self.repository.add_signature(signature)

        signature_count = len(existing_signatures) + 1

        if signature_count >= approval.required_approvers:
            approval.status = "approved"

        self.repository.session.commit()

        return self.get_approval(approval_id)

    def update_status(
        self,
        approval_id: str,
        status: str,
    ) -> ApprovalData:
        approval = self.repository.get_by_id(approval_id)

        if approval is None:
            raise ValueError(f"approval not found: {approval_id}")

        approval.status = status
        self.repository.session.commit()

        return self.get_approval(approval_id)