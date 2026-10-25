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


CLAIM_ID = "CLM-DYNAMIC-PATH-TEST"
CLAIM_EVIDENCE_ID = f"claim:{CLAIM_ID}"
CUSTOMER_ID = "CUS-DYNAMIC-TEST"
POLICY_SECTION = "section-2"


class FakeDomainLookupTool:
    """Test-only lookup tool with accurately typed synthetic evidence."""

    def __init__(self, name: str):
        self.name = name
        self.description = f"Test-only {name} lookup."
        self.calls: list[str] = []

        self.arguments_schema = {
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

    def execute(self, query: str) -> list[AgentEvidence]:
        self.calls.append(query)

        # Evidence type describes the evidence itself, not the tool name.
        # The graph's policy-grounding check therefore recognises actual
        # policy evidence without requiring a fixed investigation order.
        if self.name == "policy_lookup":
            source_type = "policy"
        elif self.name == "customer_lookup":
            source_type = "customer"
        else:
            source_type = "other"

        return [
            AgentEvidence(
                evidence_id=f"{self.name}:{query}",
                source_type=source_type,
                source_id=query,
                content=(
                    f"Synthetic {source_type} evidence retrieved "
                    f"for identifier {query}."
                ),
                locator=f"{self.name}:{query}",
                relevance=0.7,
            )
        ]


class QueueReasoningEngine(ReasoningEngine):
    """Deterministic test double used only to verify graph behaviour."""

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


def build_context() -> AgentContext:
    return AgentContext(
        run_id="RUN-DYNAMIC-PATH-TEST",
        claim_id=CLAIM_ID,
        claim={"claim_id": CLAIM_ID},
        evidence=[
            AgentEvidence(
                evidence_id=CLAIM_EVIDENCE_ID,
                source_type="claim",
                source_id=CLAIM_ID,
                content="Synthetic claim evidence for testing.",
                locator=f"claim:{CLAIM_ID}",
                relevance=1.0,
            )
        ],
    )


def make_tool_call(
    tool_name: str,
    query: str,
) -> LLMReasoningOutput:
    return LLMReasoningOutput(
        action=ReasoningAction.TOOL_CALL,
        tool_call=ToolCall(
            tool_name=tool_name,
            arguments={"query": query},
            purpose=f"Retrieve relevant information using {tool_name}.",
        ),
    )


def make_proposal(
    evidence_ids: list[str],
) -> LLMReasoningOutput:
    return LLMReasoningOutput(
        action=ReasoningAction.PROPOSAL,
        proposal=ProposalReasoning(
            recommendation="manual_review",
            tier="review",
            reasons=[
                "The cited synthetic evidence supports further review."
            ],
            evidence_ids=evidence_ids,
            confidence=0.6,
        ),
    )


def build_graph(
    engine: QueueReasoningEngine,
    tools: list[FakeDomainLookupTool],
) -> AgentGraph:
    registry = AgentToolRegistry()

    for tool in tools:
        registry.register(tool)

    validator = ReasoningOutputValidator(registry)
    executor = AgentToolExecutor(registry)

    return AgentGraph(
        reasoning_engine=engine,
        output_validator=validator,
        tool_executor=executor,
        max_iterations=8,
        max_tool_calls=8,
    )


def test_graph_honors_alternative_tool_selection_paths():
    claim_evidence_id = CLAIM_EVIDENCE_ID
    customer_evidence_id = f"customer_lookup:{CUSTOMER_ID}"
    policy_evidence_id = f"policy_lookup:{POLICY_SECTION}"

    # Path A:
    # The reasoning engine chooses customer lookup before policy lookup.
    customer_tool_a = FakeDomainLookupTool("customer_lookup")
    policy_tool_a = FakeDomainLookupTool("policy_lookup")

    engine_a = QueueReasoningEngine(
        outputs=[
            make_tool_call(
                "customer_lookup",
                CUSTOMER_ID,
            ),
            make_tool_call(
                "policy_lookup",
                POLICY_SECTION,
            ),
            make_proposal(
                [
                    claim_evidence_id,
                    customer_evidence_id,
                    policy_evidence_id,
                ]
            ),
        ]
    )

    graph_a = build_graph(
        engine_a,
        [customer_tool_a, policy_tool_a],
    )
    result_a = graph_a.invoke(build_context())

    assert result_a["status"] == "completed"
    assert result_a["proposal"] is not None
    assert result_a["proposal"].evidence_ids == [
        claim_evidence_id,
        customer_evidence_id,
        policy_evidence_id,
    ]

    assert customer_tool_a.calls == [CUSTOMER_ID]
    assert policy_tool_a.calls == [POLICY_SECTION]

    assert result_a["iteration_count"] == 3
    assert result_a["tool_call_count"] == 2

    evidence_a = {
        item.evidence_id: item
        for item in result_a["context"].evidence
    }

    assert claim_evidence_id in evidence_a
    assert customer_evidence_id in evidence_a
    assert policy_evidence_id in evidence_a
    assert evidence_a[policy_evidence_id].source_type == "policy"

    # Path B:
    # The reasoning engine chooses policy lookup before customer lookup.
    customer_tool_b = FakeDomainLookupTool("customer_lookup")
    policy_tool_b = FakeDomainLookupTool("policy_lookup")

    engine_b = QueueReasoningEngine(
        outputs=[
            make_tool_call(
                "policy_lookup",
                POLICY_SECTION,
            ),
            make_tool_call(
                "customer_lookup",
                CUSTOMER_ID,
            ),
            make_proposal(
                [
                    claim_evidence_id,
                    policy_evidence_id,
                    customer_evidence_id,
                ]
            ),
        ]
    )

    graph_b = build_graph(
        engine_b,
        [customer_tool_b, policy_tool_b],
    )
    result_b = graph_b.invoke(build_context())

    assert result_b["status"] == "completed"
    assert result_b["proposal"] is not None
    assert result_b["proposal"].evidence_ids == [
        claim_evidence_id,
        policy_evidence_id,
        customer_evidence_id,
    ]

    assert policy_tool_b.calls == [POLICY_SECTION]
    assert customer_tool_b.calls == [CUSTOMER_ID]

    assert result_b["iteration_count"] == 3
    assert result_b["tool_call_count"] == 2

    evidence_b = {
        item.evidence_id: item
        for item in result_b["context"].evidence
    }

    assert claim_evidence_id in evidence_b
    assert customer_evidence_id in evidence_b
    assert policy_evidence_id in evidence_b
    assert evidence_b[policy_evidence_id].source_type == "policy"

    # Both paths should have made their own reasoning decisions.
    assert len(engine_a.contexts) == 3
    assert len(engine_b.contexts) == 3

    # Confirm that each subsequent reasoning call received the evidence
    # accumulated by the preceding tool executions.
    assert customer_evidence_id in {
        item.evidence_id for item in engine_a.contexts[1].evidence
    }
    assert policy_evidence_id in {
        item.evidence_id for item in engine_a.contexts[2].evidence
    }

    assert policy_evidence_id in {
        item.evidence_id for item in engine_b.contexts[1].evidence
    }
    assert customer_evidence_id in {
        item.evidence_id for item in engine_b.contexts[2].evidence
    }