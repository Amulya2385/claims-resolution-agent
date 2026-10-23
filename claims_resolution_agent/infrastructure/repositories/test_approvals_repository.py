from datetime import datetime, timedelta, timezone

from claims_resolution_agent.infrastructure.database import SessionLocal
from claims_resolution_agent.infrastructure.models import (
    ApprovalRecord,
    ApprovalSignature,
    Claim,
)
from claims_resolution_agent.infrastructure.repositories.approvals import (
    ApprovalRepository,
)


def main():
    session = SessionLocal()

    try:
        claim = Claim(
            claim_id="TEST-APPROVAL-001",
            order_id="TEST-ORDER-APPROVAL-001",
            customer_id="TEST-CUSTOMER-APPROVAL-001",
            amount=340.00,
            currency="USD",
            reason="damaged",
            photo_on_file=True,
            chargeback_in_progress=False,
            customer_description="Approval repository integration test",
        )

        session.add(claim)
        session.flush()

        repository = ApprovalRepository(session)

        approval = ApprovalRecord(
            approval_id="TEST-APPROVAL-001",
            claim_id=claim.claim_id,
            payload_hash="a" * 64,
            required_approvers=1,
            status="pending",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )

        repository.add(approval)

        loaded = repository.get_by_id("TEST-APPROVAL-001")

        assert loaded is not None
        assert loaded.approval_id == "TEST-APPROVAL-001"
        assert loaded.claim_id == "TEST-APPROVAL-001"
        assert loaded.required_approvers == 1
        assert loaded.status == "pending"

        signature = ApprovalSignature(
            approval_id=approval.approval_id,
            approver_id="TEST-APPROVER-001",
            signed_at=datetime.now(timezone.utc),
        )

        repository.add_signature(signature)

        signatures = repository.get_signatures(approval.approval_id)

        assert len(signatures) == 1
        assert signatures[0].approver_id == "TEST-APPROVER-001"

        updated = repository.update_status(
            approval.approval_id,
            "approved",
        )

        assert updated.status == "approved"

        print("APPROVAL REPOSITORY: PASS")
        print(f"Approval: {loaded.approval_id}")
        print(f"Signatures: {len(signatures)}")
        print(f"Status: {updated.status}")

        session.rollback()

    finally:
        session.close()


if __name__ == "__main__":
    main()