import json
from types import SimpleNamespace

import pytest

from claims_resolution_agent.application.openai_compatible_llm import (
    OpenAICompatibleLLMClient,
)
from claims_resolution_agent.application.tool_registry import AgentToolRegistry
from claims_resolution_agent.domain.agent_models import AgentContext
from claims_resolution_agent.domain.reasoning_models import (
    LLMReasoningOutput,
    ReasoningAction,
)


class FakeTool:
    name = "search_policy_context"
    description = "Search approved policy documents."

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

    def execute(self, query: str, k: int = 4):
        return []


class FakeCompletions:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.call_arguments = None

    def create(self, **kwargs):
        self.call_arguments = kwargs

        if self.error is not None:
            raise self.error

        return self.response


class FakeLLMProvider:
    def __init__(self, response=None, error=None):
        self.completions = FakeCompletions(
            response=response,
            error=error,
        )

        self.chat = SimpleNamespace(
            completions=self.completions,
        )


def build_registry() -> AgentToolRegistry:
    registry = AgentToolRegistry()
    registry.register(FakeTool())
    return registry


def build_context() -> AgentContext:
    return AgentContext(
        run_id="RUN-LLM-TEST",
        claim_id="CLM-LLM-TEST",
        claim={
            "claim_id": "CLM-LLM-TEST",
            "reason": "item_not_received",
        },
    )


def build_response(content: str, refusal=None):
    message = SimpleNamespace(
        content=content,
        refusal=refusal,
    )

    return SimpleNamespace(
        choices=[
            SimpleNamespace(message=message),
        ]
    )


def build_client(
    response=None,
    error=None,
) -> tuple[OpenAICompatibleLLMClient, FakeLLMProvider]:
    provider = FakeLLMProvider(
        response=response,
        error=error,
    )

    client = OpenAICompatibleLLMClient(
        tool_registry=build_registry(),
        model="test-model",
        client=provider,
    )

    return client, provider


def test_generate_parses_valid_proposal():
    content = json.dumps(
        {
            "action": "proposal",
            "tool_call": None,
            "proposal": {
                "recommendation": "manual_review",
                "tier": "review",
                "reasons": [
                    "Further review is needed."
                ],
                "evidence_ids": [
                    "claim:CLM-LLM-TEST"
                ],
                "confidence": 0.6,
            },
        }
    )

    client, _ = build_client(
        response=build_response(content)
    )

    result = client.generate(build_context())

    assert isinstance(result, LLMReasoningOutput)
    assert result.action == ReasoningAction.PROPOSAL
    assert result.proposal is not None
    assert result.proposal.recommendation == "manual_review"


def test_generate_parses_valid_tool_call():
    content = json.dumps(
        {
            "action": "tool_call",
            "tool_call": {
                "tool_name": "search_policy_context",
                "arguments": {
                    "query": "item not received refund policy",
                    "k": 4,
                },
                "purpose": "Retrieve relevant policy evidence",
            },
            "proposal": None,
        }
    )

    client, _ = build_client(
        response=build_response(content)
    )

    result = client.generate(build_context())

    assert result.action == ReasoningAction.TOOL_CALL
    assert result.tool_call is not None
    assert result.tool_call.tool_name == "search_policy_context"
    assert result.tool_call.arguments["k"] == 4


def test_generate_sends_context_and_approved_tool_catalog():
    content = json.dumps(
        {
            "action": "tool_call",
            "tool_call": {
                "tool_name": "search_policy_context",
                "arguments": {
                    "query": "refund policy",
                },
                "purpose": "Retrieve policy evidence",
            },
            "proposal": None,
        }
    )

    client, provider = build_client(
        response=build_response(content)
    )

    context = build_context()
    client.generate(context)

    arguments = provider.completions.call_arguments

    assert arguments["model"] == "test-model"
    assert arguments["temperature"] == 0
    assert arguments["response_format"] == {
        "type": "json_object"
    }

    messages = arguments["messages"]

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"

    system_content = messages[0]["content"]
    user_payload = json.loads(messages[1]["content"])

    assert "search_policy_context" in system_content
    assert "additionalProperties" in system_content
    assert (
        user_payload["agent_context"]["claim_id"]
        == "CLM-LLM-TEST"
    )


def test_generate_rejects_invalid_structured_output():
    content = json.dumps(
        {
            "action": "tool_call",
            "tool_call": None,
            "proposal": None,
        }
    )

    client, _ = build_client(
        response=build_response(content)
    )

    with pytest.raises(
        ValueError,
        match="did not satisfy the reasoning contract",
    ):
        client.generate(build_context())


def test_generate_rejects_malformed_json():
    client, _ = build_client(
        response=build_response("{invalid json")
    )

    with pytest.raises(
        ValueError,
        match="did not satisfy the reasoning contract",
    ):
        client.generate(build_context())


def test_generate_rejects_empty_response_content():
    client, _ = build_client(
        response=build_response("   ")
    )

    with pytest.raises(
        RuntimeError,
        match="empty response",
    ):
        client.generate(build_context())


def test_generate_rejects_provider_refusal():
    client, _ = build_client(
        response=build_response(
            content="",
            refusal="Request refused by provider",
        )
    )

    with pytest.raises(
        RuntimeError,
        match="refused the reasoning request",
    ):
        client.generate(build_context())


def test_generate_rejects_response_without_choices():
    response = SimpleNamespace(choices=[])

    client, _ = build_client(response=response)

    with pytest.raises(
        RuntimeError,
        match="no completion choices",
    ):
        client.generate(build_context())


def test_generate_propagates_provider_failure():
    client, _ = build_client(
        error=RuntimeError("Synthetic provider failure")
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic provider failure",
    ):
        client.generate(build_context())


def test_model_must_be_configured(monkeypatch):
    monkeypatch.delenv("CLAIMS_AGENT_MODEL", raising=False)

    with pytest.raises(
        ValueError,
        match="CLAIMS_AGENT_MODEL",
    ):
        OpenAICompatibleLLMClient(
            tool_registry=build_registry(),
            client=FakeLLMProvider(),
        )