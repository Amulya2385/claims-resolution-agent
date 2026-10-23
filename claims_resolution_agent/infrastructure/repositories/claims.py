from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Claim


class ClaimRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, claim_id: str) -> Claim | None:
        statement = select(Claim).where(Claim.claim_id == claim_id)
        return self.session.scalar(statement)

    def add(self, claim: Claim) -> Claim:
        self.session.add(claim)
        self.session.flush()
        return claim