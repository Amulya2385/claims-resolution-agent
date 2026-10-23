from datetime import datetime, timezone

from claims_resolution_agent.infrastructure.database import SessionLocal
from claims_resolution_agent.infrastructure.models import Claim, RefundExecution
from claims_resolution_agent.infrastructure.repositories.refunds import (
    RefundExecutionRepository,
)


def main():
    session = SessionLocal()

    try:
        claim = Claim(
            claim_id="TEST-REFUND-001",
            order_id="TEST-ORDER-REFUND-001",
            customer_id="TEST-CUSTOMER-REFUND-001",
            amount=125.50,
            currency="USD",
            reason="wrong_item",
            photo_on_file=False,
            chargeback_in_progress=False,
            customer_description="Refund repository integration test",
        )

        session.add(claim)
        session.flush()

        repository = RefundExecutionRepository(session)

        execution = RefundExecution(
            claim_id=claim.claim_id,
            idempotency_key="TEST-IDEMPOTENCY-001",
            amount=125.50,
            currency="USD",
            tier="single",
            status="executed",
            entry_hash="b" * 64,
            executed_at=datetime.now(timezone.utc),
        )

        repository.add(execution)

        loaded = repository.get_by_id(execution.id)

        assert loaded is not None
        assert loaded.claim_id == claim.claim_id
        assert loaded.amount == 125.50
        assert loaded.currency == "USD"
        assert loaded.status == "executed"

        by_key = repository.get_by_idempotency_key(
            "TEST-IDEMPOTENCY-001"
        )

        assert by_key is not None
        assert by_key.id == execution.id

        executions = repository.get_by_claim_id(claim.claim_id)

        assert len(executions) == 1
        assert executions[0].id == execution.id

        updated = repository.update_status(
            execution.id,
            "completed",
        )

        assert updated.status == "completed"

        print("REFUND REPOSITORY: PASS")
        print(f"Execution ID: {loaded.id}")
        print(f"Idempotency key: {by_key.idempotency_key}")
        print(f"Status: {updated.status}")

        session.rollback()

    finally:
        session.close()


if __name__ == "__main__":
    main()