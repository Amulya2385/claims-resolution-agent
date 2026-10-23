from datetime import datetime, timezone

from claims_resolution_agent.infrastructure.database import SessionLocal
from claims_resolution_agent.infrastructure.models import LedgerEntry
from claims_resolution_agent.infrastructure.repositories.ledger import (
    LedgerRepository,
)


def main():
    session = SessionLocal()

    try:
        repository = LedgerRepository(session)

        first = LedgerEntry(
            tenant_id="TEST-TENANT-001",
            payload='{"event":"claim_created","claim_id":"TEST-LEDGER-001"}',
            prev_hash="0" * 64,
            entry_hash="c" * 64,
            written_at=datetime.now(timezone.utc),
        )

        repository.add(first)

        loaded = repository.get_by_sequence(first.seq)

        assert loaded is not None
        assert loaded.tenant_id == "TEST-TENANT-001"
        assert loaded.entry_hash == "c" * 64
        assert loaded.prev_hash == "0" * 64

        by_hash = repository.get_by_entry_hash("c" * 64)

        assert by_hash is not None
        assert by_hash.seq == first.seq

        entries = repository.get_by_tenant("TEST-TENANT-001")

        assert len(entries) == 1
        assert entries[0].seq == first.seq

        print("LEDGER REPOSITORY: PASS")
        print(f"Sequence: {loaded.seq}")
        print(f"Tenant: {loaded.tenant_id}")
        print(f"Entry hash: {loaded.entry_hash}")

        session.rollback()

    finally:
        session.close()


if __name__ == "__main__":
    main()