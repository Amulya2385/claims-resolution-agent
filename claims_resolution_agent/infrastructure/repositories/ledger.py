from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import LedgerEntry


class LedgerRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, entry: LedgerEntry) -> LedgerEntry:
        self.session.add(entry)
        self.session.flush()
        return entry

    def get_by_sequence(
        self,
        seq: int,
    ) -> LedgerEntry | None:
        statement = select(LedgerEntry).where(
            LedgerEntry.seq == seq
        )
        return self.session.scalar(statement)

    def get_by_entry_hash(
        self,
        entry_hash: str,
    ) -> LedgerEntry | None:
        statement = select(LedgerEntry).where(
            LedgerEntry.entry_hash == entry_hash
        )
        return self.session.scalar(statement)

    def get_by_tenant(
        self,
        tenant_id: str,
    ) -> list[LedgerEntry]:
        statement = (
            select(LedgerEntry)
            .where(LedgerEntry.tenant_id == tenant_id)
            .order_by(LedgerEntry.seq)
        )
        return list(self.session.scalars(statement).all())