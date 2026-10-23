from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from claims_resolution_agent.infrastructure.database import SessionLocal
from claims_resolution_agent.infrastructure.models import (
    ApprovalRecord,
    ApprovalSignature,
    Claim,
    LedgerEntry,
    RefundExecution,
)
from claims_resolution_agent.infrastructure.repositories.approvals import (
    ApprovalRepository,
)
from claims_resolution_agent.infrastructure.repositories.claims import (
    ClaimRepository,
)
from claims_resolution_agent.infrastructure.repositories.ledger import (
    LedgerRepository,
)
from claims_resolution_agent.infrastructure.repositories.refunds import (
    RefundExecutionRepository,
)


def test_claim_approval_signature_persistence():
    session = SessionLocal()

    try:
        claim = Claim(
            claim_id="TEST-G-001",
            order_id="TEST-G-ORDER-001",
            customer_id="TEST-G-CUSTOMER-001",
            amount=100.00,
            currency="USD",
            reason="damaged",
            photo_on_file=True,
            chargeback_in_progress=False,
            customer_description="Sprint 1 persistence test",
        )

        claim_repository = ClaimRepository(session)
        claim_repository.add(claim)

        approval = ApprovalRecord(
            approval_id="TEST-G-APPROVAL-001",
            claim_id=claim.claim_id,
            payload_hash="a" * 64,
            required_approvers=1,
            status="pending",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc),
        )

        approval_repository = ApprovalRepository(session)
        approval_repository.add(approval)

        signature = ApprovalSignature(
            approval_id=approval.approval_id,
            approver_id="TEST-G-APPROVER-001",
            signed_at=datetime.now(timezone.utc),
        )

        approval_repository.add_signature(signature)
        session.flush()

        loaded_claim = claim_repository.get_by_id("TEST-G-001")
        loaded_approval = approval_repository.get_by_id(
            "TEST-G-APPROVAL-001"
        )

        assert loaded_claim is not None
        assert loaded_claim.claim_id == "TEST-G-001"
        assert loaded_claim.amount == 100.00

        assert loaded_approval is not None
        assert loaded_approval.claim_id == "TEST-G-001"
        assert loaded_approval.required_approvers == 1

        assert len(loaded_approval.signatures) == 1
        assert (
            loaded_approval.signatures[0].approver_id
            == "TEST-G-APPROVER-001"
        )

        print("PERSISTENCE RELATIONSHIP: PASS")
        print(f"Claim: {loaded_claim.claim_id}")
        print(f"Approval: {loaded_approval.approval_id}")
        print(f"Signatures: {len(loaded_approval.signatures)}")

    finally:
        session.rollback()
        session.close()


def test_duplicate_approval_signature_is_rejected():
    session = SessionLocal()

    try:
        claim = Claim(
            claim_id="TEST-G-002",
            order_id="TEST-G-ORDER-002",
            customer_id="TEST-G-CUSTOMER-002",
            amount=200.00,
            currency="USD",
            reason="wrong_item",
            photo_on_file=False,
            chargeback_in_progress=False,
        )

        claim_repository = ClaimRepository(session)
        claim_repository.add(claim)

        approval = ApprovalRecord(
            approval_id="TEST-G-APPROVAL-002",
            claim_id=claim.claim_id,
            payload_hash="b" * 64,
            required_approvers=1,
            status="pending",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc),
        )

        approval_repository = ApprovalRepository(session)
        approval_repository.add(approval)

        first_signature = ApprovalSignature(
            approval_id=approval.approval_id,
            approver_id="TEST-G-APPROVER-002",
            signed_at=datetime.now(timezone.utc),
        )

        approval_repository.add_signature(first_signature)
        session.flush()

        duplicate_signature = ApprovalSignature(
            approval_id=approval.approval_id,
            approver_id="TEST-G-APPROVER-002",
            signed_at=datetime.now(timezone.utc),
        )

        try:
            approval_repository.add_signature(duplicate_signature)
            session.flush()
        except IntegrityError:
            session.rollback()
            print("DUPLICATE SIGNATURE CONSTRAINT: PASS")
        else:
            raise AssertionError(
                "Duplicate approval signature was accepted unexpectedly"
            )

    finally:
        session.rollback()
        session.close()


def test_refund_idempotency_constraint():
    session = SessionLocal()

    try:
        claim = Claim(
            claim_id="TEST-G-003",
            order_id="TEST-G-ORDER-003",
            customer_id="TEST-G-CUSTOMER-003",
            amount=300.00,
            currency="USD",
            reason="damaged",
            photo_on_file=True,
            chargeback_in_progress=False,
        )

        claim_repository = ClaimRepository(session)
        claim_repository.add(claim)

        repository = RefundExecutionRepository(session)

        first_execution = RefundExecution(
            claim_id=claim.claim_id,
            idempotency_key="TEST-G-IDEMPOTENCY-001",
            amount=300.00,
            currency="USD",
            tier="single",
            status="completed",
            entry_hash="d" * 64,
            executed_at=datetime.now(timezone.utc),
        )

        repository.add(first_execution)
        session.flush()

        duplicate_execution = RefundExecution(
            claim_id=claim.claim_id,
            idempotency_key="TEST-G-IDEMPOTENCY-001",
            amount=300.00,
            currency="USD",
            tier="single",
            status="completed",
            entry_hash="e" * 64,
            executed_at=datetime.now(timezone.utc),
        )

        try:
            repository.add(duplicate_execution)
            session.flush()
        except IntegrityError:
            session.rollback()
            print("REFUND IDEMPOTENCY CONSTRAINT: PASS")
        else:
            raise AssertionError(
                "Duplicate refund idempotency key was accepted unexpectedly"
            )

    finally:
        session.rollback()
        session.close()


def test_ledger_entry_hash_constraint():
    session = SessionLocal()

    try:
        repository = LedgerRepository(session)

        first_entry = LedgerEntry(
            tenant_id="TEST-G-TENANT-001",
            payload="Sprint 1 ledger test",
            prev_hash="0" * 64,
            entry_hash="f" * 64,
            written_at=datetime.now(timezone.utc),
        )

        repository.add(first_entry)
        session.flush()

        duplicate_entry = LedgerEntry(
            tenant_id="TEST-G-TENANT-001",
            payload="Duplicate Sprint 1 ledger test",
            prev_hash="1" * 64,
            entry_hash="f" * 64,
            written_at=datetime.now(timezone.utc),
        )

        try:
            repository.add(duplicate_entry)
            session.flush()
        except IntegrityError:
            session.rollback()
            print("LEDGER ENTRY HASH CONSTRAINT: PASS")
        else:
            raise AssertionError(
                "Duplicate ledger entry hash was accepted unexpectedly"
            )

    finally:
        session.rollback()
        session.close()


if __name__ == "__main__":
    test_claim_approval_signature_persistence()
    test_duplicate_approval_signature_is_rejected()
    test_refund_idempotency_constraint()
    test_ledger_entry_hash_constraint()

    print("ALL PERSISTENCE TESTS: PASS")