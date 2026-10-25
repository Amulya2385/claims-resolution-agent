import pytest

from claims_resolution_agent.application.reasoning_validator import (
    ReasoningOutputValidator,
)
from claims_resolution_agent.application.tool_registry import AgentToolRegistry
from claims_resolution_agent.domain.agent_models import (
    AgentContext,
    AgentEvidence,
    ToolCall,
)
from claims_resolution_agent.domain.reasoning_models import (
    LLMReasoningOutput,
    ProposalReasoning,
    ReasoningAction,
)


class FakeValidatorTool:
    name = "test_tool"
    description = "Test-only tool for validator unit tests."

    arguments_schema = {
        "type": "object",
        "properties": {
            "value": {"type": "string"},
        },
        "required": ["value"],
        "additionalProperties": False,
    }

    def __init__(self):
        self.execution_count = 0

    def execute(self, **kwargs):
        self.execution_count += 1
        return []


def build_registry() -> AgentToolRegistry:
    registry = AgentToolRegistry()
    registry.register(FakeValidatorTool())
    return registry


def build_context() -> AgentContext:
    return AgentContext(
        run_id="RUN-TEST-001",
        claim_id="CLM-TEST-001",
        claim={"claim_id": "CLM-TEST-001"},
        evidence=[
            AgentEvidence(
                evidence_id="claim:CLM-TEST-001",
                source_type="claim",
                source_id="CLM-TEST-001",
                content="Claim evidence for validator testing.",
                locator="claim:CLM-TEST-001",
                relevance=1.0,
            )
        ],
        tool_calls=[],
        reasoning_steps=[],
    )


def test_valid_tool_call_is_accepted():
    validator = ReasoningOutputValidator(build_registry())
    context = build_context()

    output = LLMReasoningOutput(
        action=ReasoningAction.TOOL_CALL,
        tool_call=ToolCall(
            tool_name="test_tool",
            arguments={"value": "test"},
            purpose="Retrieve additional information",
        ),
    )

    result = validator.validate(output, context)

    assert result == output


def test_unknown_tool_is_rejected():
    validator = ReasoningOutputValidator(build_registry())
    context = build_context()

    output = LLMReasoningOutput(
        action=ReasoningAction.TOOL_CALL,
        tool_call=ToolCall(
            tool_name="unknown_tool",
            arguments={"value": "test"},
            purpose="Retrieve information",
        ),
    )

    with pytest.raises(ValueError, match="unknown agent tool"):
        validator.validate(output, context)


def test_tool_call_requires_tool_payload():
    validator = ReasoningOutputValidator(build_registry())
    context = build_context()

    output = LLMReasoningOutput.model_construct(
        action=ReasoningAction.TOOL_CALL,
        tool_call=None,
        proposal=None,
    )

    with pytest.raises(
        ValueError,
        match="tool_call is required",
    ):
        validator.validate(output, context)


def test_invalid_tool_arguments_are_rejected():
    tool = FakeValidatorTool()
    registry = AgentToolRegistry()
    registry.register(tool)

    validator = ReasoningOutputValidator(registry)
    context = build_context()

    output = LLMReasoningOutput(
        action=ReasoningAction.TOOL_CALL,
        tool_call=ToolCall(
            tool_name="test_tool",
            arguments={"unexpected": "value"},
            purpose="Test rejection of undeclared arguments",
        ),
    )

    with pytest.raises(
        ValueError,
        match="invalid arguments for agent tool",
    ):
        validator.validate(output, context)

    assert tool.execution_count == 0


def test_missing_required_tool_argument_is_rejected():
    validator = ReasoningOutputValidator(build_registry())
    context = build_context()

    output = LLMReasoningOutput(
        action=ReasoningAction.TOOL_CALL,
        tool_call=ToolCall(
            tool_name="test_tool",
            arguments={},
            purpose="Test required argument validation",
        ),
    )

    with pytest.raises(
        ValueError,
        match="invalid arguments for agent tool",
    ):
        validator.validate(output, context)


def test_valid_proposal_is_accepted():
    validator = ReasoningOutputValidator(build_registry())
    context = build_context()

    output = LLMReasoningOutput(
        action=ReasoningAction.PROPOSAL,
        proposal=ProposalReasoning(
            recommendation="approve",
            tier="standard",
            reasons=["Claim evidence supports the recommendation."],
            evidence_ids=["claim:CLM-TEST-001"],
            confidence=0.9,
        ),
    )

    result = validator.validate(output, context)

    assert result == output


def test_proposal_referencing_missing_evidence_is_rejected():
    validator = ReasoningOutputValidator(build_registry())
    context = build_context()

    output = LLMReasoningOutput(
        action=ReasoningAction.PROPOSAL,
        proposal=ProposalReasoning(
            recommendation="approve",
            tier="standard",
            reasons=[
                "This proposal references unavailable evidence."
            ],
            evidence_ids=["claim:DOES-NOT-EXIST"],
            confidence=0.9,
        ),
    )

    with pytest.raises(
        ValueError,
        match="proposal references unavailable evidence",
    ):
        validator.validate(output, context)


def test_proposal_requires_proposal_payload():
    validator = ReasoningOutputValidator(build_registry())
    context = build_context()

    output = LLMReasoningOutput.model_construct(
        action=ReasoningAction.PROPOSAL,
        tool_call=None,
        proposal=None,
    )

    with pytest.raises(
        ValueError,
        match="proposal is required",
    ):
        validator.validate(output, context)