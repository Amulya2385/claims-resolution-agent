from claims_resolution_agent.infrastructure.database import SessionLocal
from claims_resolution_agent.infrastructure.models import Claim
from claims_resolution_agent.infrastructure.repositories.claims import ClaimRepository


def main():
    session = SessionLocal()

    try:
        repository = ClaimRepository(session)

        claim = Claim(
            claim_id="TEST-REPO-001",
            order_id="TEST-ORDER-001",
            customer_id="TEST-CUSTOMER-001",
            amount=125.50,
            currency="USD",
            reason="wrong_item",
            photo_on_file=False,
            chargeback_in_progress=False,
            customer_description="Repository integration test",
        )

        repository.add(claim)

        loaded = repository.get_by_id("TEST-REPO-001")

        assert loaded is not None
        assert loaded.claim_id == "TEST-REPO-001"
        assert loaded.amount == 125.50
        assert loaded.currency == "USD"
        assert loaded.customer_id == "TEST-CUSTOMER-001"

        print("CLAIM REPOSITORY: PASS")
        print(f"Retrieved claim: {loaded.claim_id}")
        print(f"Amount: {loaded.amount:.2f} {loaded.currency}")

        session.rollback()

    finally:
        session.close()


if __name__ == "__main__":
    main()