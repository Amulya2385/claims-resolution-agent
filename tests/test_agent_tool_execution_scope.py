from types import SimpleNamespace

import pytest

from claims_resolution_agent.application.agent_executor import AgentToolExecutor
from claims_resolution_agent.application.agent_graph import AgentGraph
from claims_resolution_agent.application.agent_tools import (
    ClaimContextTool,
    CustomerContextTool,
    PolicyContextTool,
)
from claims_resolution_agent.application.reasoning import ReasoningEngine
from claims_resolution_agent.application.reasoning_validator import (
    ReasoningOutputValidator,
)
from claims_resolution_agent.application.tool_registry import AgentToolRegistry
from claims_resolution_agent.domain.agent_models import (
    AgentContext,
    ToolCall,
)
from claims_resolution_agent.domain.reasoning_models import (
    LLMReasoningOutput,
    ReasoningAction,
)


class SpyClaimService:
    def __init__(self):
        self.calls = []

    def get_claim(self, claim_id):
        self.calls.append(claim_id)
        return None


class SpyCustomerService:
    def __init__(self):
        self.calls = []

    def get_customer(self, customer_id):
        self.calls.append(customer_id)
        return SimpleNamespace(
            customer_id=customer_id,
            approved_refunds_trailing_90d=1,
        )


class SpyPolicyService:
    def __init__(self):
        self.calls = []

    def search_policy(self, query, k):
        self.calls.append((query, k))
        return [
            SimpleNamespace(
                doc_id="POL-001",
                locator="section-2",
                heading="Refund eligibility",
                text="Synthetic policy-search result for testing.",
                rrf_score=0.75,
            )
        ]


class SingleOutputReasoningEngine(ReasoningEngine):
    def __init__(self, output):
        self.output = output

    def reason(self, context):
        return self.output


def build_context():
    return AgentContext(
        run_id="RUN-SCOPE-INTEGRATION",
        claim_id="CLM-001",
        claim={
            "claim_id": "CLM-001",
            "customer_id": "CUS-001",
        },
    )


def build_tool_call(tool_name, arguments):
    return ToolCall(
        tool_name=tool_name,
        arguments=arguments,
        purpose="Scope integration test.",
    )


def build_registry(tool):
    registry = AgentToolRegistry()
    registry.register(tool)
    return registry


def test_executor_rejects_different_claim_before_service_access():
    service = SpyClaimService()
    registry = build_registry(ClaimContextTool(service))
    executor = AgentToolExecutor(registry)

    with pytest.raises(
        ValueError,
        match="only access the active claim",
    ):
        executor.execute(
            build_tool_call(
                "get_claim_context",
                {"claim_id": "CLM-OTHER"},
            ),
            context=build_context(),
        )

    assert service.calls == []


def test_executor_rejects_different_customer_before_service_access():
    service = SpyCustomerService()
    registry = build_registry(CustomerContextTool(service))
    executor = AgentToolExecutor(registry)

    with pytest.raises(
        ValueError,
        match="only access the customer associated",
    ):
        executor.execute(
            build_tool_call(
                "get_customer_context",
                {"customer_id": "CUS-OTHER"},
            ),
            context=build_context(),
        )

    assert service.calls == []


def test_reasoning_validator_rejects_different_customer():
    service = SpyCustomerService()
    registry = build_registry(CustomerContextTool(service))
    validator = ReasoningOutputValidator(registry)

    output = LLMReasoningOutput(
        action=ReasoningAction.TOOL_CALL,
        tool_call=build_tool_call(
            "get_customer_context",
            {"customer_id": "CUS-OTHER"},
        ),
    )

    with pytest.raises(
        ValueError,
        match="only access the customer associated",
    ):
        validator.validate(output, build_context())

    assert service.calls == []


def test_graph_rejects_different_customer_before_retrieval():
    service = SpyCustomerService()
    registry = build_registry(CustomerContextTool(service))

    output = LLMReasoningOutput(
        action=ReasoningAction.TOOL_CALL,
        tool_call=build_tool_call(
            "get_customer_context",
            {"customer_id": "CUS-OTHER"},
        ),
    )

    graph = AgentGraph(
        reasoning_engine=SingleOutputReasoningEngine(output),
        output_validator=ReasoningOutputValidator(registry),
        tool_executor=AgentToolExecutor(registry),
        max_iterations=3,
        max_tool_calls=3,
    )

    result = graph.invoke(build_context())

    assert result["status"] == "failed"
    assert result["proposal"] is None
    assert "validation failed" in result["error"]
    assert service.calls == []


def test_valid_customer_access_still_works():
    service = SpyCustomerService()
    registry = build_registry(CustomerContextTool(service))
    executor = AgentToolExecutor(registry)

    result = executor.execute(
        build_tool_call(
            "get_customer_context",
            {"customer_id": "CUS-001"},
        ),
        context=build_context(),
    )

    assert service.calls == ["CUS-001"]
    assert len(result) == 1
    assert result[0].evidence_id == "customer:CUS-001"


def test_policy_search_remains_available_through_executor():
    service = SpyPolicyService()
    registry = build_registry(PolicyContextTool(service))
    executor = AgentToolExecutor(registry)

    result = executor.execute(
        build_tool_call(
            "search_policy_context",
            {
                "query": "item not received refund eligibility",
                "k": 3,
            },
        ),
        context=build_context(),
    )

    assert service.calls == [
        ("item not received refund eligibility", 3)
    ]
    assert len(result) == 1
    assert result[0].source_type == "policy"
    assert result[0].source_id == "POL-001"