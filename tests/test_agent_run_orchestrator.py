
from datetime import datetime, timezone

from claims_resolution_agent.application.agent_run_orchestrator import (
    AgentRunOrchestrator,
)
from claims_resolution_agent.domain.agent_models import (
    AgentContext,
    AgentEvidence,
)
from claims_resolution_agent.domain.models import (
    AgentRunData,
    ClaimData,
    CustomerData,
    DecisionData,
)
from claims_resolution_agent.domain.reasoning_models import ProposalReasoning
from claims_resolution_agent.server.classification import classify


RUN_ID = "RUN-ORCHESTRATOR-001"
CLAIM_ID = "CLM-ORCHESTRATOR-001"
CUSTOMER_ID = "CUS-ORCHESTRATOR-001"

POLICY_CLAUSE = (
    "refund-authorization#Clause 6 — Authorization Thresholds"
)
POLICY_EVIDENCE_ID = (
    f"policy:refund-authorization:{POLICY_CLAUSE}"
)

WRONG_POLICY_CLAUSE = (
    "refund-authorization#Clause 8 — Damage Claims"
)
WRONG_POLICY_EVIDENCE_ID = (
    f"policy:refund-authorization:{WRONG_POLICY_CLAUSE}"
)


def build_claim() -> ClaimData:
    return ClaimData(
        claim_id=CLAIM_ID,
        order_id="ORD-ORCHESTRATOR-001",
        customer_id=CUSTOMER_ID,
        amount=100.0,
        currency="USD",
        reason="item_not_received",
        photo_on_file=False,
        chargeback_in_progress=False,
        customer_description="Test claim description.",
    )


def build_run(status: str = "started") -> AgentRunData:
    return AgentRunData(
        run_id=RUN_ID,
        claim_id=CLAIM_ID,
        status=status,
        started_at=datetime.now(timezone.utc),
    )


def build_proposal(
    evidence_ids: list[str] | None = None,
    tier: str = "review",
) -> ProposalReasoning:
    return ProposalReasoning(
        recommendation="manual_review",
        tier=tier,
        reasons=["Available evidence supports further review."],
        evidence_ids=evidence_ids or [
            f"claim:{CLAIM_ID}",
            POLICY_EVIDENCE_ID,
        ],
        confidence=0.6,
    )


class FakeAgentRunService:
    def __init__(self, run: AgentRunData | None = None):
        self.run = run
        self.status_updates = []

    def get_agent_run(self, run_id: str):
        if self.run is None or self.run.run_id != run_id:
            return None
        return self.run

    def update_status(
        self,
        run_id: str,
        status: str,
        error_message: str | None = None,
    ):
        if self.run is None or self.run.run_id != run_id:
            raise ValueError(f"agent run not found: {run_id}")

        self.status_updates.append((status, error_message))
        self.run = self.run.model_copy(
            update={
                "status": status,
                "error_message": error_message,
                "completed_at": (
                    datetime.now(timezone.utc)
                    if status in {"completed", "failed"}
                    else self.run.completed_at
                ),
            }
        )
        return self.run


class FakeClaimService:
    def __init__(self, claim: ClaimData | None = None):
        self.claim = claim
        self.requests = []

    def get_claim(self, claim_id: str):
        self.requests.append(claim_id)
        if self.claim is None or self.claim.claim_id != claim_id:
            return None
        return self.claim


class FakeCustomerService:
    def __init__(self):
        self.requests = []
        self.customer = CustomerData(
            customer_id=CUSTOMER_ID,
            approved_refunds_trailing_90d=0,
        )

    def get_customer(self, customer_id: str):
        self.requests.append(customer_id)

        if self.customer is None:
            return None

        if self.customer.customer_id != customer_id:
            return None

        return self.customer


class FakeDecisionService:
    def __init__(self):
        self.created_decisions = []

    def create_decision(self, **kwargs):
        self.created_decisions.append(kwargs)

        return DecisionData(
            decision_id=kwargs["decision_id"],
            run_id=kwargs["run_id"],
            claim_id=kwargs["claim_id"],
            tier=kwargs["tier"],
            recommendation=kwargs["recommendation"],
            reasons=kwargs["reasons"],
            policy_clause=kwargs["policy_clause"],
            status=kwargs["status"],
            created_at=datetime.now(timezone.utc),
        )


class FakeAuditEventService:
    def __init__(self):
        self.events = []

    def create_event(self, **kwargs):
        self.events.append(kwargs)


class FakeAgentGraph:
    def __init__(
        self,
        status: str = "completed",
        include_policy: bool = True,
        proposal: ProposalReasoning | None = None,
        error: str | None = None,
        policy_clause: str = POLICY_CLAUSE,
    ):
        self.status = status
        self.include_policy = include_policy
        self.proposal = proposal
        self.error = error
        self.policy_clause = policy_clause
        self.received_context = None

    def invoke(self, context: AgentContext) -> dict:
        self.received_context = context.model_copy(deep=True)

        if self.include_policy:
            document_id = self.policy_clause.split("#", 1)[0]
            policy_evidence_id = (
                f"policy:{document_id}:{self.policy_clause}"
            )

            self.received_context.evidence.append(
                AgentEvidence(
                    evidence_id=policy_evidence_id,
                    source_type="policy",
                    source_id=document_id,
                    content="Synthetic policy evidence for testing.",
                    locator=self.policy_clause,
                    relevance=0.025,
                )
            )

        proposal = self.proposal

        if proposal is None and self.status == "completed":
            proposal = build_proposal()

        return {
            "context": self.received_context,
            "proposal": (
                proposal if self.status == "completed" else None
            ),
            "status": self.status,
            "error": self.error,
            "tool_call_count": 1,
            "iteration_count": 2,
        }


def build_orchestrator(
    *,
    run: AgentRunData | None = None,
    claim: ClaimData | None = None,
    graph: FakeAgentGraph | None = None,
):
    run_service = FakeAgentRunService(run or build_run())
    claim_service = FakeClaimService(
        build_claim() if claim is None else claim
    )
    customer_service = FakeCustomerService()
    decision_service = FakeDecisionService()
    audit_service = FakeAuditEventService()
    agent_graph = graph or FakeAgentGraph()

    orchestrator = AgentRunOrchestrator(
        agent_run_service=run_service,
        claim_service=claim_service,
        customer_service=customer_service,
        decision_service=decision_service,
        audit_event_service=audit_service,
        agent_graph=agent_graph,
        claim_classifier=classify,
    )

    return (
        orchestrator,
        run_service,
        claim_service,
        decision_service,
        audit_service,
        agent_graph,
    )


def test_successful_run_uses_authoritative_tier_and_audit_events():
    (
        orchestrator,
        run_service,
        _,
        decision_service,
        audit_service,
        graph,
    ) = build_orchestrator()

    result = orchestrator.execute(RUN_ID)

    assert result.graph_status == "completed"
    assert result.agent_run.status == "completed"
    assert result.decision is not None
    assert result.decision.status == "proposed"
    assert result.decision.claim_id == CLAIM_ID
    assert result.decision.run_id == RUN_ID

    # The faculty classifier, not model tier="review", is authoritative.
    assert result.decision.tier == "routine"
    assert result.decision.policy_clause == POLICY_CLAUSE

    assert len(decision_service.created_decisions) == 1
    persisted = decision_service.created_decisions[0]
    assert persisted["status"] == "proposed"
    assert persisted["tier"] == "routine"
    assert persisted["policy_clause"] == POLICY_CLAUSE
    assert (
        "amount 100.00 is at or below the routine threshold"
        in persisted["reasons"]
    )
    assert (
        "Available evidence supports further review."
        in persisted["reasons"]
    )

    assert run_service.status_updates == [("completed", None)]

    assert [
        event["event_type"] for event in audit_service.events
    ] == [
        "agent_execution_started",
        "agent_proposal_created",
    ]

    proposal_event = audit_service.events[-1]["payload"]
    assert proposal_event["execution_authority"] == "proposal_only"
    assert proposal_event["model_proposed_tier"] == "review"
    assert proposal_event["authoritative_tier"] == "routine"
    assert (
        proposal_event["classification_policy_clause"] == POLICY_CLAUSE
    )
    assert POLICY_EVIDENCE_ID in (
        proposal_event["referenced_evidence_ids"]
    )
    assert graph.received_context is not None


def test_failed_graph_marks_run_failed_and_records_audit():
    graph = FakeAgentGraph(
        status="failed",
        error="Synthetic reasoning failure.",
    )

    (
        orchestrator,
        run_service,
        _,
        decision_service,
        audit_service,
        _,
    ) = build_orchestrator(graph=graph)

    result = orchestrator.execute(RUN_ID)

    assert result.agent_run.status == "failed"
    assert result.decision is None
    assert "Synthetic reasoning failure" in result.error_message
    assert decision_service.created_decisions == []
    assert run_service.status_updates[0][0] == "failed"

    assert [
        event["event_type"] for event in audit_service.events
    ] == [
        "agent_execution_started",
        "agent_execution_failed",
    ]


def test_proposal_without_policy_evidence_is_not_persisted():
    graph = FakeAgentGraph(
        include_policy=False,
        proposal=build_proposal([f"claim:{CLAIM_ID}"]),
    )

    (
        orchestrator,
        run_service,
        _,
        decision_service,
        audit_service,
        _,
    ) = build_orchestrator(graph=graph)

    result = orchestrator.execute(RUN_ID)

    assert result.graph_status == "proposal_rejected"
    assert result.agent_run.status == "failed"
    assert result.decision is None
    assert "does not reference retrieved policy evidence" in (
        result.error_message
    )
    assert decision_service.created_decisions == []
    assert audit_service.events[-1]["event_type"] == (
        "agent_execution_failed"
    )


def test_proposal_citing_wrong_policy_clause_is_rejected():
    graph = FakeAgentGraph(
        policy_clause=WRONG_POLICY_CLAUSE,
        proposal=build_proposal(
            [
                f"claim:{CLAIM_ID}",
                WRONG_POLICY_EVIDENCE_ID,
            ]
        ),
    )

    (
        orchestrator,
        run_service,
        _,
        decision_service,
        audit_service,
        _,
    ) = build_orchestrator(graph=graph)

    result = orchestrator.execute(RUN_ID)

    assert result.graph_status == "proposal_rejected"
    assert result.decision is None
    assert "exact policy clause required" in result.error_message
    assert decision_service.created_decisions == []
    assert run_service.status_updates[-1][0] == "failed"
    assert audit_service.events[-1]["event_type"] == (
        "agent_execution_failed"
    )


def test_missing_customer_history_fails_closed_after_agent_proposal():
    (
        orchestrator,
        run_service,
        _,
        decision_service,
        audit_service,
        graph,
    ) = build_orchestrator()

    orchestrator.customer_service.customer = None

    result = orchestrator.execute(RUN_ID)

    # Investigation runs first; governance then fails closed.
    assert graph.received_context is not None
    assert result.graph_status == "classification_failed"
    assert result.agent_run.status == "failed"
    assert result.decision is None
    assert decision_service.created_decisions == []
    assert run_service.status_updates[-1][0] == "failed"
    assert audit_service.events[-1]["event_type"] == (
        "agent_execution_failed"
    )


def test_missing_claim_fails_without_invoking_graph():
    (
        orchestrator,
        run_service,
        claim_service,
        decision_service,
        audit_service,
        graph,
    ) = build_orchestrator(claim=None)

    # The factory creates a normal claim by default; simulate a missing one.
    claim_service.claim = None

    result = orchestrator.execute(RUN_ID)

    assert result.agent_run.status == "failed"
    assert result.decision is None
    assert result.evidence_count == 0
    assert graph.received_context is None
    assert claim_service.requests == [CLAIM_ID]
    assert decision_service.created_decisions == []
    assert run_service.status_updates[0][0] == "failed"
    assert audit_service.events[-1]["event_type"] == (
        "agent_execution_failed"
    )


def test_run_not_found_is_rejected():
    orchestrator, run_service, *_ = build_orchestrator()
    run_service.run = None

    try:
        orchestrator.execute(RUN_ID)
    except ValueError as exc:
        assert f"agent run not found: {RUN_ID}" in str(exc)
    else:
        raise AssertionError("Expected missing run to be rejected")


def test_non_started_run_cannot_be_executed_again():
    orchestrator, *_ = build_orchestrator(
        run=build_run(status="completed")
    )

    try:
        orchestrator.execute(RUN_ID)
    except ValueError as exc:
        assert "cannot be executed from status 'completed'" in str(exc)
    else:
        raise AssertionError("Expected completed run to be rejected")
