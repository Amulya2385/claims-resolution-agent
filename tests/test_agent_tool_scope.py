
import pytest

from claims_resolution_agent.application.agent_tools import (
    ClaimContextTool,
    CustomerContextTool,
    PolicyContextTool,
)
from claims_resolution_agent.domain.agent_models import AgentContext


def build_context(
    claim_id: str = "CLM-001",
    customer_id: str | None = "CUS-001",
    context_claim_id: str | None = None,
) -> AgentContext:
    stored_claim_id = context_claim_id or claim_id

    claim = {"claim_id": stored_claim_id}

    if customer_id is not None:
        claim["customer_id"] = customer_id

    return AgentContext(
        run_id="RUN-SCOPE-TEST",
        claim_id=claim_id,
        claim=claim,
    )


def test_claim_tool_accepts_the_active_claim():
    tool = ClaimContextTool(claim_service=object())
    context = build_context()

    tool.validate_context(
        context,
        {"claim_id": "CLM-001"},
    )


def test_claim_tool_rejects_a_different_claim():
    tool = ClaimContextTool(claim_service=object())
    context = build_context()

    with pytest.raises(
        ValueError,
        match="only access the active claim",
    ):
        tool.validate_context(
            context,
            {"claim_id": "CLM-OTHER"},
        )


def test_claim_tool_rejects_inconsistent_context():
    tool = ClaimContextTool(claim_service=object())
    context = build_context(context_claim_id="CLM-OTHER")

    with pytest.raises(
        ValueError,
        match="does not match the active claim",
    ):
        tool.validate_context(
            context,
            {"claim_id": "CLM-001"},
        )


def test_customer_tool_accepts_the_active_claims_customer():
    tool = CustomerContextTool(customer_service=object())
    context = build_context()

    tool.validate_context(
        context,
        {"customer_id": "CUS-001"},
    )


def test_customer_tool_rejects_an_unrelated_customer():
    tool = CustomerContextTool(customer_service=object())
    context = build_context()

    with pytest.raises(
        ValueError,
        match="only access the customer associated",
    ):
        tool.validate_context(
            context,
            {"customer_id": "CUS-OTHER"},
        )


def test_customer_tool_fails_closed_if_customer_id_is_missing():
    tool = CustomerContextTool(customer_service=object())
    context = build_context(customer_id=None)

    with pytest.raises(
        ValueError,
        match="does not contain a valid customer ID",
    ):
        tool.validate_context(
            context,
            {"customer_id": "CUS-001"},
        )


def test_policy_tool_allows_dynamic_search_for_active_claim():
    tool = PolicyContextTool(policy_service=object())
    context = build_context()

    tool.validate_context(
        context,
        {"query": "item not received refund eligibility", "k": 4},
    )


def test_policy_tool_rejects_an_empty_query():
    tool = PolicyContextTool(policy_service=object())
    context = build_context()

    with pytest.raises(
        ValueError,
        match="query cannot be empty",
    ):
        tool.validate_context(
            context,
            {"query": "   "},
    )
