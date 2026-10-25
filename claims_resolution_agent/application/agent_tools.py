
from typing import Any

from claims_resolution_agent.application.services.claims import ClaimService
from claims_resolution_agent.application.services.customers import CustomerService
from claims_resolution_agent.application.services.policies import PolicyService
from claims_resolution_agent.domain.agent_models import AgentContext, AgentEvidence
from claims_resolution_agent.domain.models import ClaimData, CustomerData


def _validate_active_claim_context(context: AgentContext) -> None:
    """Ensure the run ID and claim ID agree with the trusted claim record."""
    if not context.claim_id.strip():
        raise ValueError("Active claim ID cannot be empty.")

    context_claim_id = context.claim.get("claim_id")

    if context_claim_id != context.claim_id:
        raise ValueError(
            "Agent context claim ID does not match the active claim."
        )


class ClaimContextTool:
    name = "get_claim_context"

    description = (
        "Retrieve the authoritative claim record for the active claim. "
        "The claim ID must match the claim being investigated."
    )

    arguments_schema = {
        "type": "object",
        "properties": {
            "claim_id": {
                "type": "string",
                "minLength": 1,
            },
        },
        "required": ["claim_id"],
        "additionalProperties": False,
    }

    def __init__(self, claim_service: ClaimService):
        self.claim_service = claim_service

    def validate_context(
        self,
        context: AgentContext,
        arguments: dict[str, Any],
    ) -> None:
        _validate_active_claim_context(context)

        if arguments.get("claim_id") != context.claim_id:
            raise ValueError(
                "Claim context tool may only access the active claim."
            )

    def execute(self, claim_id: str) -> list[AgentEvidence]:
        if not claim_id.strip():
            raise ValueError("claim_id cannot be empty")

        claim = self.claim_service.get_claim(claim_id)

        if claim is None:
            raise ValueError("Requested claim could not be retrieved.")

        return [
            AgentEvidence(
                evidence_id=f"claim:{claim.claim_id}",
                source_type="claim",
                source_id=claim.claim_id,
                content=self._serialize_claim(claim),
                locator=f"claim:{claim.claim_id}",
                relevance=1.0,
            )
        ]

    @staticmethod
    def _serialize_claim(claim: ClaimData) -> str:
        return (
            f"claim_id={claim.claim_id}; "
            f"order_id={claim.order_id}; "
            f"customer_id={claim.customer_id}; "
            f"amount={claim.amount}; "
            f"currency={claim.currency}; "
            f"reason={claim.reason}; "
            f"photo_on_file={claim.photo_on_file}; "
            f"chargeback_in_progress={claim.chargeback_in_progress}; "
            f"customer_description={claim.customer_description}"
        )


class CustomerContextTool:
    name = "get_customer_context"

    description = (
        "Retrieve the customer record and recorded refund history "
        "for the customer associated with the active claim."
    )

    arguments_schema = {
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "string",
                "minLength": 1,
            },
        },
        "required": ["customer_id"],
        "additionalProperties": False,
    }

    def __init__(self, customer_service: CustomerService):
        self.customer_service = customer_service

    def validate_context(
        self,
        context: AgentContext,
        arguments: dict[str, Any],
    ) -> None:
        _validate_active_claim_context(context)

        active_customer_id = context.claim.get("customer_id")

        if (
            not isinstance(active_customer_id, str)
            or not active_customer_id.strip()
        ):
            raise ValueError(
                "Active claim does not contain a valid customer ID."
            )

        if arguments.get("customer_id") != active_customer_id:
            raise ValueError(
                "Customer context tool may only access the customer "
                "associated with the active claim."
            )

    def execute(self, customer_id: str) -> list[AgentEvidence]:
        if not customer_id.strip():
            raise ValueError("customer_id cannot be empty")

        customer = self.customer_service.get_customer(customer_id)

        if customer is None:
            raise ValueError("Requested customer could not be retrieved.")

        return [
            AgentEvidence(
                evidence_id=f"customer:{customer.customer_id}",
                source_type="customer",
                source_id=customer.customer_id,
                content=self._serialize_customer(customer),
                locator=f"customer:{customer.customer_id}",
                relevance=1.0,
            )
        ]

    @staticmethod
    def _serialize_customer(customer: CustomerData) -> str:
        return (
            f"customer_id={customer.customer_id}; "
            "approved_refunds_trailing_90d="
            f"{customer.approved_refunds_trailing_90d}"
        )


class PolicyContextTool:
    name = "search_policy_context"

    description = (
        "Search the existing policy index for relevant policy clauses. "
        "Choose a focused natural-language query based on the claim "
        "and the evidence already available."
    )

    arguments_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "minLength": 1,
            },
            "k": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, policy_service: PolicyService):
        self.policy_service = policy_service

    def validate_context(
        self,
        context: AgentContext,
        arguments: dict[str, Any],
    ) -> None:
        # Policy lookup can be selected dynamically, but must still be
        # associated with a consistent, valid active claim context.
        _validate_active_claim_context(context)

        query = arguments.get("query")

        if not isinstance(query, str) or not query.strip():
            raise ValueError("Policy search query cannot be empty.")

    def execute(
        self,
        query: str,
        k: int = 4,
    ) -> list[AgentEvidence]:
        if not query.strip():
            raise ValueError("policy search query cannot be empty")

        results = self.policy_service.search_policy(
            query=query,
            k=k,
        )

        return [
            AgentEvidence(
                evidence_id=f"policy:{result.doc_id}:{result.locator}",
                source_type="policy",
                source_id=result.doc_id,
                content=f"heading={result.heading}; text={result.text}",
                locator=result.locator,
                relevance=result.rrf_score,
            )
            for result in results
        ]
