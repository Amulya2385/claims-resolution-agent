from claims_resolution_agent.domain.models import ClaimData
from claims_resolution_agent.infrastructure.models import Claim
from claims_resolution_agent.infrastructure.repositories.claims import ClaimRepository


class ClaimService:
    def __init__(self, repository: ClaimRepository):
        self.repository = repository

    def get_claim(self, claim_id: str) -> ClaimData | None:
        claim = self.repository.get_by_id(claim_id)

        if claim is None:
            return None

        return ClaimData(
            claim_id=claim.claim_id,
            order_id=claim.order_id,
            customer_id=claim.customer_id,
            amount=claim.amount,
            currency=claim.currency,
            reason=claim.reason,
            photo_on_file=claim.photo_on_file,
            chargeback_in_progress=claim.chargeback_in_progress,
            customer_description=claim.customer_description,
        )

    def create_claim(self, data: ClaimData) -> ClaimData:
        existing = self.repository.get_by_id(data.claim_id)

        if existing is not None:
            raise ValueError(f"claim already exists: {data.claim_id}")

        claim = Claim(
            claim_id=data.claim_id,
            order_id=data.order_id,
            customer_id=data.customer_id,
            amount=data.amount,
            currency=data.currency,
            reason=data.reason,
            photo_on_file=data.photo_on_file,
            chargeback_in_progress=data.chargeback_in_progress,
            customer_description=data.customer_description,
        )

        self.repository.add(claim)

        self.repository.session.commit()

        return data