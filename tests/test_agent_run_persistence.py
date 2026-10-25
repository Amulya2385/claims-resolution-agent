
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from claims_resolution_agent.application.agent_run_orchestrator import (
    AgentRunOrchestrator,
)
from claims_resolution_agent.application.services.agent_runs import (
    AgentRunService,
)
from claims_resolution_agent.application.services.audit_events import (
    AuditEventService,
)
from claims_resolution_agent.application.services.claims import ClaimService
from claims_resolution_agent.application.services.customers import (
    CustomerService,
)
from claims_resolution_agent.application.services.decisions import (
    DecisionService,
)
from claims_resolution_agent.domain.agent_models import (
    AgentContext,
    AgentEvidence,
)
from claims_resolution_agent.domain.models import ClaimData, CustomerData
from claims_resolution_agent.domain.reasoning_models import ProposalReasoning
from claims_resolution_agent.infrastructure import models as orm_models
from claims_resolution_agent.infrastructure.base import Base
from claims_resolution_agent.infrastructure.repositories.agent_runs import (
    AgentRunRepository,
)
from claims_resolution_agent.infrastructure.repositories.audit_events import (
    AuditEventRepository,
)
from claims_resolution_agent.infrastructure.repositories.claims import (
    ClaimRepository,
)
from claims_resolution_agent.infrastructure.repositories.customers import (
    CustomerRepository,
)
from claims_resolution_agent.infrastructure.repositories.decisions import (
    DecisionRepository,
)
from claims_resolution_agent.server.classification import classify


RUN_ID = "RUN-PERSIST-001"
CLAIM_ID = "CLM-PERSIST-001"
CUSTOMER_ID = "CUS-PERSIST-001"

POLICY_CLAUSE = (
    "refund-authorization#Clause 6 — Authorization Thresholds"
)
POLICY_EVIDENCE_ID = (
    f"policy:refund-authorization:{POLICY_CLAUSE}"
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


def build_claim() -> ClaimData:
    return ClaimData(
        claim_id=CLAIM_ID,
        order_id="ORD-PERSIST-001",
        customer_id=CUSTOMER_ID,
        amount=100.0,
        currency="USD",
        reason="item_not_received",
        photo_on_file=False,
        chargeback_in_progress=False,
        customer_description="Persistence integration test.",
    )


class FakeAgentGraph:
    """Scripted graph used only to test orchestrator persistence."""

    def __init__(
        self,
        *,
        status: str = "completed",
        include_policy: bool = True,
    ):
        self.status = status
        self.include_policy = include_policy

    def invoke(self, context: AgentContext) -> dict:
        final_context = context.model_copy(deep=True)

        if self.include_policy:
            final_context.evidence.append(
                AgentEvidence(
                    evidence_id=POLICY_EVIDENCE_ID,
                    source_type="policy",
                    source_id="refund-authorization",
                    content=(
                        "Synthetic policy evidence for persistence testing."
                    ),
                    locator=POLICY_CLAUSE,
                    relevance=0.025,
                )
            )

        proposal = None

        if self.status == "completed":
            evidence_ids = (
                [f"claim:{CLAIM_ID}", POLICY_EVIDENCE_ID]
                if self.include_policy
                else [f"claim:{CLAIM_ID}"]
            )

            proposal = ProposalReasoning(
                recommendation="manual_review",
                tier="review",
                reasons=[
                    "The recorded test evidence supports further review."
                ],
                evidence_ids=evidence_ids,
                confidence=0.6,
            )

        return {
            "context": final_context,
            "proposal": proposal,
            "status": self.status,
            "error": (
                None
                if self.status == "completed"
                else "Synthetic graph failure."
            ),
            "tool_call_count": 1,
            "iteration_count": 2,
        }


def build_orchestrator(
    session: Session,
    *,
    graph: FakeAgentGraph | None = None,
):
    claim_service = ClaimService(ClaimRepository(session))
    customer_service = CustomerService(CustomerRepository(session))
    run_service = AgentRunService(AgentRunRepository(session))
    decision_service = DecisionService(DecisionRepository(session))
    audit_service = AuditEventService(AuditEventRepository(session))

    # The real customer service is required by the faculty classifier.
    customer_service.create_customer(
        CustomerData(
            customer_id=CUSTOMER_ID,
            approved_refunds_trailing_90d=0,
        )
    )

    claim_service.create_claim(build_claim())
    run_service.create_agent_run(
        run_id=RUN_ID,
        claim_id=CLAIM_ID,
    )

    orchestrator = AgentRunOrchestrator(
        agent_run_service=run_service,
        claim_service=claim_service,
        customer_service=customer_service,
        decision_service=decision_service,
        audit_event_service=audit_service,
        agent_graph=graph or FakeAgentGraph(),
        claim_classifier=classify,
    )

    return (
        orchestrator,
        run_service,
        decision_service,
        audit_service,
    )


def test_successful_proposal_is_persisted_and_read_back(db_session):
    (
        orchestrator,
        run_service,
        decision_service,
        audit_service,
    ) = build_orchestrator(db_session)

    result = orchestrator.execute(RUN_ID)

    assert result.graph_status == "completed"
    assert result.agent_run.status == "completed"
    assert result.decision is not None
    assert result.decision.status == "proposed"

    # The faculty classifier, not the model's tier, is authoritative.
    assert result.decision.tier == "routine"
    assert result.decision.policy_clause == POLICY_CLAUSE

    db_session.expire_all()

    stored_run = run_service.get_agent_run(RUN_ID)
    stored_decision = decision_service.get_decision(
        result.decision.decision_id
    )

    assert stored_run is not None
    assert stored_run.status == "completed"
    assert stored_run.completed_at is not None

    assert stored_decision is not None
    assert stored_decision.status == "proposed"
    assert stored_decision.tier == "routine"
    assert stored_decision.policy_clause == POLICY_CLAUSE
    assert (
        "amount 100.00 is at or below the routine threshold"
        in stored_decision.reasons
    )
    assert (
        "The recorded test evidence supports further review."
        in stored_decision.reasons
    )

    stored_events = AuditEventRepository(
        db_session
    ).get_by_run_id(RUN_ID)

    assert {item.event_type for item in stored_events} == {
        "agent_execution_started",
        "agent_proposal_created",
    }

    proposal_record = next(
        item
        for item in stored_events
        if item.event_type == "agent_proposal_created"
    )

    # Read through the service so JSON payload parsing follows the
    # existing application contract.
    proposal_event = audit_service.get_event(
        proposal_record.event_id
    )

    assert proposal_event is not None
    assert proposal_event.payload["decision_id"] == (
        result.decision.decision_id
    )
    assert proposal_event.payload["execution_authority"] == (
        "proposal_only"
    )
    assert proposal_event.payload["model_proposed_tier"] == "review"
    assert proposal_event.payload["authoritative_tier"] == "routine"
    assert POLICY_EVIDENCE_ID in (
        proposal_event.payload["referenced_evidence_ids"]
    )


def test_failed_graph_persists_failed_run_and_audit(db_session):
    (
        orchestrator,
        run_service,
        decision_service,
        audit_service,
    ) = build_orchestrator(
        db_session,
        graph=FakeAgentGraph(status="failed"),
    )

    result = orchestrator.execute(RUN_ID)

    assert result.agent_run.status == "failed"
    assert result.decision is None

    db_session.expire_all()

    stored_run = run_service.get_agent_run(RUN_ID)

    assert stored_run is not None
    assert stored_run.status == "failed"
    assert stored_run.completed_at is not None
    assert "Synthetic graph failure" in stored_run.error_message

    assert DecisionRepository(db_session).get_by_run_id(RUN_ID) == []

    events = AuditEventRepository(db_session).get_by_run_id(RUN_ID)

    assert {item.event_type for item in events} == {
        "agent_execution_started",
        "agent_execution_failed",
    }

    failed_record = next(
        item
        for item in events
        if item.event_type == "agent_execution_failed"
    )

    failed_event = audit_service.get_event(failed_record.event_id)

    assert failed_event is not None
    assert failed_event.payload["graph_status"] == "failed"


def test_proposal_without_policy_evidence_is_not_persisted(db_session):
    (
        orchestrator,
        run_service,
        _,
        audit_service,
    ) = build_orchestrator(
        db_session,
        graph=FakeAgentGraph(include_policy=False),
    )

    result = orchestrator.execute(RUN_ID)

    assert result.graph_status == "proposal_rejected"
    assert result.decision is None

    db_session.expire_all()

    stored_run = run_service.get_agent_run(RUN_ID)

    assert stored_run is not None
    assert stored_run.status == "failed"

    assert DecisionRepository(db_session).get_by_run_id(RUN_ID) == []

    events = AuditEventRepository(db_session).get_by_run_id(RUN_ID)

    failed_record = next(
        item
        for item in events
        if item.event_type == "agent_execution_failed"
    )

    failed_event = audit_service.get_event(failed_record.event_id)

    assert failed_event is not None
    assert "does not reference retrieved policy evidence" in (
        failed_event.payload["error"]
    )
