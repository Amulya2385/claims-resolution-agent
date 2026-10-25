
from types import SimpleNamespace

import pytest

from claims_resolution_agent.application.agent_factory import (
    build_claim_agent_graph,
)
from claims_resolution_agent.application.llm import LLMClient
from claims_resolution_agent.domain.agent_models import AgentContext, ToolCall
from claims_resolution_agent.domain.reasoning_models import (
    LLMReasoningOutput,
    ProposalReasoning,
    ReasoningAction,
)


class FakeClaimService:
    def __init__(self):
        self.requested_claim_ids = []

    def get_claim(self, claim_id: str):
        self.requested_claim_ids.append(claim_id)

        if claim_id != "CLM-FACTORY-001":
            return None

        return SimpleNamespace(
            claim_id=claim_id,
            order_id="ORD-FACTORY-001",
            customer_id="CUS-FACTORY-001",
            amount=100.0,
            currency="USD",
            reason="item_not_received",
            photo_on_file=False,
            chargeback_in_progress=False,
            customer_description="The item was not received.",
        )


class FakeCustomerService:
    def __init__(self):
        self.requested_customer_ids = []

    def get_customer(self, customer_id: str):
        self.requested_customer_ids.append(customer_id)

        if customer_id != "CUS-FACTORY-001":
            return None

        return SimpleNamespace(
            customer_id=customer_id,
            approved_refunds_trailing_90d=0,
        )


class FakePolicyService:
    def __init__(self):
        self.searches = []

    def search_policy(self, query: str, k: int = 4):
        self.searches.append((query, k))

        return [
            SimpleNamespace(
                doc_id="POL-FACTORY-001",
                locator="section-2",
                heading="Item not received",
                text="Synthetic policy evidence for factory testing.",
                rrf_score=0.025,
            )
        ]


class ContextDrivenFakeLLM(LLMClient):
    """Produces test actions based on evidence currently in the context."""

    def generate(
        self,
        context: AgentContext,
    ) -> LLMReasoningOutput:
        evidence_types = {
            item.source_type for item in context.evidence
        }

        if "claim" not in evidence_types:
            return LLMReasoningOutput(
                action=ReasoningAction.TOOL_CALL,
                tool_call=ToolCall(
                    tool_name="get_claim_context",
                    arguments={"claim_id": context.claim_id},
                    purpose="Retrieve the claim record",
                ),
            )

        if "customer" not in evidence_types:
            return LLMReasoningOutput(
                action=ReasoningAction.TOOL_CALL,
                tool_call=ToolCall(
                    tool_name="get_customer_context",
                    arguments={
                        "customer_id": context.claim["customer_id"]
                    },
                    purpose="Retrieve customer context",
                ),
            )

        if "policy" not in evidence_types:
            return LLMReasoningOutput(
                action=ReasoningAction.TOOL_CALL,
                tool_call=ToolCall(
                    tool_name="search_policy_context",
                    arguments={
                        "query": "item not received",
                        "k": 1,
                    },
                    purpose="Retrieve relevant policy evidence",
                ),
            )

        return LLMReasoningOutput(
            action=ReasoningAction.PROPOSAL,
            proposal=ProposalReasoning(
                recommendation="manual_review",
                tier="review",
                reasons=[
                    "The available test evidence is ready for review."
                ],
                evidence_ids=[
                    item.evidence_id for item in context.evidence
                ],
                confidence=0.6,
            ),
        )


def build_services():
    return (
        FakeClaimService(),
        FakeCustomerService(),
        FakePolicyService(),
    )


def build_context() -> AgentContext:
    return AgentContext(
        run_id="RUN-FACTORY-001",
        claim_id="CLM-FACTORY-001",
        claim={
            "claim_id": "CLM-FACTORY-001",
            "customer_id": "CUS-FACTORY-001",
        },
    )


def test_factory_connects_services_and_completes_investigation():
    claim_service, customer_service, policy_service = build_services()

    graph = build_claim_agent_graph(
        claim_service=claim_service,
        customer_service=customer_service,
        policy_service=policy_service,
        llm_client=ContextDrivenFakeLLM(),
    )

    result = graph.invoke(build_context())

    assert result["status"] == "completed"
    assert result["proposal"] is not None

    assert claim_service.requested_claim_ids == [
        "CLM-FACTORY-001"
    ]
    assert customer_service.requested_customer_ids == [
        "CUS-FACTORY-001"
    ]
    assert policy_service.searches == [
        ("item not received", 1)
    ]

    evidence_types = {
        item.source_type for item in result["context"].evidence
    }

    assert evidence_types == {"claim", "customer", "policy"}
    assert result["tool_call_count"] == 3
    assert result["iteration_count"] == 4

    evidence_ids = {
        item.evidence_id for item in result["context"].evidence
    }

    assert set(result["proposal"].evidence_ids) == evidence_ids


def test_factory_rejects_model_options_when_client_is_injected():
    claim_service, customer_service, policy_service = build_services()

    with pytest.raises(
        ValueError,
        match="cannot be supplied when llm_client is injected",
    ):
        build_claim_agent_graph(
            claim_service=claim_service,
            customer_service=customer_service,
            policy_service=policy_service,
            llm_client=ContextDrivenFakeLLM(),
            model="test-model",
        )


def test_factory_rejects_nonpositive_iteration_limit():
    claim_service, customer_service, policy_service = build_services()

    with pytest.raises(
        ValueError,
        match="CLAIMS_AGENT_MAX_ITERATIONS must be a positive integer",
    ):
        build_claim_agent_graph(
            claim_service=claim_service,
            customer_service=customer_service,
            policy_service=policy_service,
            llm_client=ContextDrivenFakeLLM(),
            max_iterations=0,
        )


def test_factory_rejects_nonpositive_tool_call_limit():
    claim_service, customer_service, policy_service = build_services()

    with pytest.raises(
        ValueError,
        match="CLAIMS_AGENT_MAX_TOOL_CALLS must be a positive integer",
    ):
        build_claim_agent_graph(
            claim_service=claim_service,
            customer_service=customer_service,
            policy_service=policy_service,
            llm_client=ContextDrivenFakeLLM(),
            max_tool_calls=0,
        )


def test_factory_requires_model_configuration_without_injected_client(
    monkeypatch,
):
    monkeypatch.delenv("CLAIMS_AGENT_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CLAIMS_AGENT_API_KEY", raising=False)

    claim_service, customer_service, policy_service = build_services()

    with pytest.raises(
        ValueError,
        match="CLAIMS_AGENT_MODEL",
    ):
        build_claim_agent_graph(
            claim_service=claim_service,
            customer_service=customer_service,
            policy_service=policy_service,
        )
