import pytest

from claims_resolution_agent.application.llm import LLMClient
from claims_resolution_agent.application.llm_reasoning_engine import (
    LLMReasoningEngine,
)
from claims_resolution_agent.domain.agent_models import AgentContext
from claims_resolution_agent.domain.reasoning_models import (
    LLMReasoningOutput,
    ProposalReasoning,
    ReasoningAction,
)


class FakeLLMClient(LLMClient):
    def __init__(self, output):
        self.output = output
        self.received_context = None
        self.call_count = 0

    def generate(self, context: AgentContext) -> LLMReasoningOutput:
        self.received_context = context
        self.call_count += 1

        if isinstance(self.output, Exception):
            raise self.output

        return self.output


def build_context() -> AgentContext:
    return AgentContext(
        run_id="RUN-LLM-ENGINE-TEST",
        claim_id="CLM-LLM-ENGINE-TEST",
        claim={"claim_id": "CLM-LLM-ENGINE-TEST"},
    )


def build_proposal_output() -> LLMReasoningOutput:
    return LLMReasoningOutput(
        action=ReasoningAction.PROPOSAL,
        proposal=ProposalReasoning(
            recommendation="manual_review",
            tier="review",
            reasons=["Further review is required."],
            evidence_ids=["claim:CLM-LLM-ENGINE-TEST"],
            confidence=0.6,
        ),
    )


def test_reasoning_engine_returns_typed_llm_output():
    context = build_context()
    output = build_proposal_output()
    client = FakeLLMClient(output)

    engine = LLMReasoningEngine(client)

    result = engine.reason(context)

    assert result == output
    assert client.received_context is context
    assert client.call_count == 1


def test_reasoning_engine_rejects_untyped_llm_output():
    context = build_context()
    client = FakeLLMClient({"action": "proposal"})

    engine = LLMReasoningEngine(client)

    with pytest.raises(
        TypeError,
        match="must return LLMReasoningOutput",
    ):
        engine.reason(context)


def test_reasoning_engine_propagates_llm_failure():
    context = build_context()
    client = FakeLLMClient(
        RuntimeError("Synthetic provider failure")
    )

    engine = LLMReasoningEngine(client)

    with pytest.raises(
        RuntimeError,
        match="Synthetic provider failure",
    ):
        engine.reason(context)