import pytest
from pydantic import ValidationError

from claims_resolution_agent.domain.agent_models import ToolCall
from claims_resolution_agent.domain.reasoning_models import (
    LLMReasoningOutput,
    ProposalReasoning,
    ReasoningAction,
)


def make_tool_call() -> ToolCall:
    return ToolCall(
        tool_name="search_policy_context",
        arguments={"query": "refund eligibility"},
        purpose="Retrieve relevant policy evidence",
    )


def make_proposal() -> ProposalReasoning:
    return ProposalReasoning(
        recommendation="manual_review",
        tier="review",
        reasons=["The available evidence requires further assessment."],
        evidence_ids=["policy:document-1:section-2"],
        confidence=0.7,
    )


def test_valid_tool_call_output():
    output = LLMReasoningOutput(
        action=ReasoningAction.TOOL_CALL,
        tool_call=make_tool_call(),
    )

    assert output.action == ReasoningAction.TOOL_CALL
    assert output.tool_call is not None
    assert output.proposal is None


def test_valid_proposal_output():
    output = LLMReasoningOutput(
        action=ReasoningAction.PROPOSAL,
        proposal=make_proposal(),
    )

    assert output.action == ReasoningAction.PROPOSAL
    assert output.proposal is not None
    assert output.tool_call is None


def test_tool_call_action_requires_tool_call():
    with pytest.raises(ValidationError, match="tool_call is required"):
        LLMReasoningOutput(action=ReasoningAction.TOOL_CALL)


def test_tool_call_action_rejects_proposal():
    with pytest.raises(
        ValidationError,
        match="proposal must be absent",
    ):
        LLMReasoningOutput(
            action=ReasoningAction.TOOL_CALL,
            tool_call=make_tool_call(),
            proposal=make_proposal(),
        )


def test_proposal_action_requires_proposal():
    with pytest.raises(ValidationError, match="proposal is required"):
        LLMReasoningOutput(action=ReasoningAction.PROPOSAL)


def test_proposal_action_rejects_tool_call():
    with pytest.raises(
        ValidationError,
        match="tool_call must be absent",
    ):
        LLMReasoningOutput(
            action=ReasoningAction.PROPOSAL,
            proposal=make_proposal(),
            tool_call=make_tool_call(),
        )