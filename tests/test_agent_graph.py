from claims_resolution_agent.application.agent_executor import AgentToolExecutor
from claims_resolution_agent.application.agent_graph import AgentGraph
from claims_resolution_agent.application.reasoning import ReasoningEngine
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


class FakeLookupTool:
    name = "lookup"
    description = "Test-only tool that returns synthetic evidence."

    arguments_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "minLength": 1,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, fail_queries: set[str] | None = None):
        self.fail_queries = fail_queries or set()
        self.calls: list[str] = []

    def execute(self, query: str) -> list[AgentEvidence]:
        self.calls.append(query)

        if query in self.fail_queries:
            raise RuntimeError("Synthetic tool failure")

        if query == "policy":
            source_type = "policy"
        elif query == "customer":
            source_type = "customer"
        else:
            source_type = "test_tool"

        return [
            AgentEvidence(
                evidence_id=f"tool:{query}",
                source_type=source_type,
                source_id=query,
                content=f"Synthetic evidence retrieved for {query}.",
                locator=f"test:{query}",
                relevance=0.5,
            )
        ]


class QueueReasoningEngine(ReasoningEngine):
    def __init__(self, outputs: list[LLMReasoningOutput]):
        self.outputs = list(outputs)
        self.contexts: list[AgentContext] = []

    def reason(self, context: AgentContext) -> LLMReasoningOutput:
        self.contexts.append(context.model_copy(deep=True))

        if not self.outputs:
            raise AssertionError(
                "The reasoning engine received more calls than expected."
            )

        return self.outputs.pop(0)


class FailingReasoningEngine(ReasoningEngine):
    def reason(self, context: AgentContext) -> LLMReasoningOutput:
        raise RuntimeError("Synthetic reasoning failure")


def build_context(
    include_policy: bool = False,
    include_customer: bool = False,
) -> AgentContext:
    evidence = [
        AgentEvidence(
            evidence_id="claim:CLM-GRAPH-TEST",
            source_type="claim",
            source_id="CLM-GRAPH-TEST",
            content="Synthetic claim evidence.",
            locator="claim:CLM-GRAPH-TEST",
            relevance=1.0,
        )
    ]

    if include_policy:
        evidence.append(
            AgentEvidence(
                evidence_id="policy:seed",
                source_type="policy",
                source_id="POL-TEST",
                content="Synthetic policy evidence for graph testing.",
                locator="section-2",
                relevance=0.5,
            )
        )

    if include_customer:
        evidence.append(
            AgentEvidence(
                evidence_id="customer:seed",
                source_type="customer",
                source_id="CUS-TEST",
                content="approved_refunds_trailing_90d=0",
                locator="customer:CUS-TEST",
                relevance=1.0,
            )
        )

    return AgentContext(
        run_id="RUN-GRAPH-TEST",
        claim_id="CLM-GRAPH-TEST",
        claim={"claim_id": "CLM-GRAPH-TEST"},
        evidence=evidence,
    )


def make_tool_call(query: str) -> LLMReasoningOutput:
    return LLMReasoningOutput(
        action=ReasoningAction.TOOL_CALL,
        tool_call=ToolCall(
            tool_name="lookup",
            arguments={"query": query},
            purpose=f"Retrieve evidence about {query}",
        ),
    )


def make_proposal(
    evidence_ids: list[str],
    reasons: list[str] | None = None,
) -> LLMReasoningOutput:
    return LLMReasoningOutput(
        action=ReasoningAction.PROPOSAL,
        proposal=ProposalReasoning(
            recommendation="manual_review",
            tier="review",
            reasons=reasons
            or ["The cited evidence supports further review."],
            evidence_ids=evidence_ids,
            confidence=0.6,
        ),
    )


def build_graph(
    reasoning_engine: ReasoningEngine,
    tool: FakeLookupTool | None = None,
    max_iterations: int = 8,
    max_tool_calls: int = 8,
) -> tuple[AgentGraph, FakeLookupTool]:
    lookup_tool = tool or FakeLookupTool()

    registry = AgentToolRegistry()
    registry.register(lookup_tool)

    validator = ReasoningOutputValidator(registry)
    executor = AgentToolExecutor(registry)

    graph = AgentGraph(
        reasoning_engine=reasoning_engine,
        output_validator=validator,
        tool_executor=executor,
        max_iterations=max_iterations,
        max_tool_calls=max_tool_calls,
    )

    return graph, lookup_tool


def test_agent_graph_completes_multistep_investigation():
    engine = QueueReasoningEngine(
        outputs=[
            make_tool_call("order"),
            make_tool_call("policy"),
            make_proposal(["tool:order", "tool:policy"]),
        ]
    )
    graph, tool = build_graph(engine)

    result = graph.invoke(build_context())

    assert result["status"] == "completed"
    assert result["proposal"] is not None
    assert result["proposal"].evidence_ids == [
        "tool:order",
        "tool:policy",
    ]

    assert result["iteration_count"] == 3
    assert result["tool_call_count"] == 2
    assert tool.calls == ["order", "policy"]

    evidence_ids = {
        item.evidence_id
        for item in result["context"].evidence
    }
    assert "tool:order" in evidence_ids
    assert "tool:policy" in evidence_ids

    assert len(result["context"].tool_calls) == 2
    assert result["context"].reasoning_steps[-1].action == (
        "proposal_created"
    )


def test_agent_graph_accepts_direct_policy_grounded_proposal():
    engine = QueueReasoningEngine(
        outputs=[
            make_proposal(
                [
                    "claim:CLM-GRAPH-TEST",
                    "policy:seed",
                ]
            ),
        ]
    )
    graph, tool = build_graph(engine)

    result = graph.invoke(
        build_context(include_policy=True)
    )

    assert result["status"] == "completed"
    assert result["iteration_count"] == 1
    assert result["tool_call_count"] == 0
    assert result["proposal"] is not None
    assert tool.calls == []


def test_agent_graph_reinvestigates_premature_policy_proposal():
    engine = QueueReasoningEngine(
        outputs=[
            make_proposal(["claim:CLM-GRAPH-TEST"]),
            make_tool_call("policy"),
            make_proposal(
                [
                    "claim:CLM-GRAPH-TEST",
                    "tool:policy",
                ]
            ),
        ]
    )
    graph, tool = build_graph(engine)

    result = graph.invoke(build_context())

    assert result["status"] == "completed"
    assert result["iteration_count"] == 3
    assert result["tool_call_count"] == 1
    assert tool.calls == ["policy"]

    assert (
        engine.contexts[1].reasoning_steps[-1].action
        == "proposal_rejected_insufficient_policy_evidence"
    )

    assert result["proposal"] is not None
    assert result["proposal"].evidence_ids == [
        "claim:CLM-GRAPH-TEST",
        "tool:policy",
    ]


def test_agent_graph_reinvestigates_unsupported_customer_history_claim():
    history_reason = (
        "The customer has no prior refunds in the trailing 90 days."
    )

    engine = QueueReasoningEngine(
        outputs=[
            make_tool_call("policy"),
            make_proposal(
                [
                    "claim:CLM-GRAPH-TEST",
                    "tool:policy",
                ],
                reasons=[history_reason],
            ),
            make_tool_call("customer"),
            make_proposal(
                [
                    "claim:CLM-GRAPH-TEST",
                    "tool:policy",
                    "tool:customer",
                ],
                reasons=[history_reason],
            ),
        ]
    )

    graph, tool = build_graph(engine)
    result = graph.invoke(build_context())

    assert result["status"] == "completed"
    assert result["iteration_count"] == 4
    assert result["tool_call_count"] == 2
    assert tool.calls == ["policy", "customer"]

    assert result["proposal"] is not None
    assert result["proposal"].evidence_ids == [
        "claim:CLM-GRAPH-TEST",
        "tool:policy",
        "tool:customer",
    ]

    assert (
        engine.contexts[2].reasoning_steps[-1].action
        == "proposal_rejected_insufficient_customer_evidence"
    )

    final_evidence = {
        item.evidence_id: item
        for item in result["context"].evidence
    }

    assert final_evidence["tool:customer"].source_type == "customer"


def test_agent_graph_rejects_history_claim_when_customer_evidence_is_not_cited():
    engine = QueueReasoningEngine(
        outputs=[
            make_proposal(
                [
                    "claim:CLM-GRAPH-TEST",
                    "policy:seed",
                ],
                reasons=[
                    "The customer has no prior refunds in the trailing 90 days."
                ],
            ),
        ]
    )

    graph, _ = build_graph(
        engine,
        max_iterations=1,
    )

    result = graph.invoke(
        build_context(
            include_policy=True,
            include_customer=True,
        )
    )

    assert result["status"] == "limit_reached"
    assert result["proposal"] is None

    # The customer record exists in context, but the proposal did not
    # cite it. Mere availability is not sufficient for grounding.
    actions = [
        step.action
        for step in result["context"].reasoning_steps
    ]

    assert (
        "proposal_rejected_insufficient_customer_evidence"
        in actions
    )
    assert actions[-1] == "limit_reached"


def test_agent_graph_stops_at_limit_after_premature_proposal():
    engine = QueueReasoningEngine(
        outputs=[
            make_proposal(["claim:CLM-GRAPH-TEST"]),
        ]
    )
    graph, tool = build_graph(
        engine,
        max_iterations=1,
    )

    result = graph.invoke(build_context())

    assert result["status"] == "limit_reached"
    assert result["proposal"] is None
    assert result["iteration_count"] == 1
    assert tool.calls == []

    assert any(
        step.action == "proposal_rejected_insufficient_policy_evidence"
        for step in result["context"].reasoning_steps
    )
    assert result["context"].reasoning_steps[-1].action == (
        "limit_reached"
    )


def test_agent_graph_rejects_proposal_with_missing_evidence():
    engine = QueueReasoningEngine(
        outputs=[
            make_proposal(["evidence:not-present"]),
        ]
    )
    graph, _ = build_graph(engine)

    result = graph.invoke(build_context())

    assert result["status"] == "failed"
    assert result["proposal"] is None
    assert "validation failed" in result["error"]

    actions = [
        step.action
        for step in result["context"].reasoning_steps
    ]
    assert "validation_failed" in actions


def test_agent_graph_stops_before_tool_execution_at_iteration_limit():
    engine = QueueReasoningEngine(
        outputs=[
            make_tool_call("order"),
        ]
    )
    graph, tool = build_graph(
        engine,
        max_iterations=1,
        max_tool_calls=8,
    )

    result = graph.invoke(build_context())

    assert result["status"] == "limit_reached"
    assert result["proposal"] is None
    assert result["iteration_count"] == 1
    assert result["tool_call_count"] == 0
    assert tool.calls == []
    assert result["context"].tool_calls == []


def test_agent_graph_enforces_tool_call_budget():
    engine = QueueReasoningEngine(
        outputs=[
            make_tool_call("order"),
            make_tool_call("policy"),
        ]
    )
    graph, tool = build_graph(
        engine,
        max_iterations=5,
        max_tool_calls=1,
    )

    result = graph.invoke(build_context())

    assert result["status"] == "limit_reached"
    assert result["proposal"] is None
    assert result["tool_call_count"] == 1
    assert tool.calls == ["order"]


def test_agent_graph_recovers_from_tool_failure():
    engine = QueueReasoningEngine(
        outputs=[
            make_tool_call("broken"),
            make_tool_call("policy"),
            make_proposal(
                [
                    "claim:CLM-GRAPH-TEST",
                    "tool:policy",
                ]
            ),
        ]
    )
    tool = FakeLookupTool(fail_queries={"broken"})
    graph, _ = build_graph(engine, tool=tool)

    result = graph.invoke(build_context())

    assert result["status"] == "completed"
    assert result["proposal"] is not None
    assert result["iteration_count"] == 3
    assert result["tool_call_count"] == 2
    assert tool.calls == ["broken", "policy"]

    assert len(engine.contexts) == 3
    assert engine.contexts[1].reasoning_steps[-1].action == (
        "tool_call_failed"
    )


def test_agent_graph_rejects_unregistered_tool():
    engine = QueueReasoningEngine(
        outputs=[
            LLMReasoningOutput(
                action=ReasoningAction.TOOL_CALL,
                tool_call=ToolCall(
                    tool_name="unregistered_tool",
                    arguments={},
                    purpose="Attempt an unregistered tool",
                ),
            ),
        ]
    )
    graph, tool = build_graph(engine)

    result = graph.invoke(build_context())

    assert result["status"] == "failed"
    assert result["proposal"] is None
    assert tool.calls == []


def test_agent_graph_records_reasoning_failure():
    graph, _ = build_graph(FailingReasoningEngine())

    result = graph.invoke(build_context())

    assert result["status"] == "failed"
    assert result["proposal"] is None
    assert result["iteration_count"] == 1
    assert result["error"] == "Reasoning engine failed (RuntimeError)."

    assert result["context"].reasoning_steps[-1].action == (
        "reasoning_failed"
    )