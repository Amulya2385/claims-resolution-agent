
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from claims_resolution_agent.application.agent_factory import (
    build_claim_agent_graph,
)
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
from claims_resolution_agent.application.services.policies import (
    PolicyService,
)
from claims_resolution_agent.domain.models import (
    AgentRunData,
    DecisionData,
)
from claims_resolution_agent.infrastructure.database import SessionLocal
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
from claims_resolution_agent.server.classification import (
    classify as faculty_classify,
)


router = APIRouter(
    prefix="/api/v1/agent-runs",
    tags=["agent-execution"],
)


class AgentRunExecutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_run: AgentRunData
    decision: DecisionData | None = None
    graph_status: str
    evidence_count: int = Field(ge=0)
    tool_call_count: int = Field(ge=0)
    error_message: str | None = None


def get_db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


def get_agent_run_orchestrator(
    session: Session = Depends(get_db),
) -> AgentRunOrchestrator:
    # Existing application services and repositories remain the
    # source of truth for claims, customers, runs, decisions and audits.
    claim_service = ClaimService(
        ClaimRepository(session)
    )
    customer_service = CustomerService(
        CustomerRepository(session)
    )
    policy_service = PolicyService()

    agent_run_service = AgentRunService(
        AgentRunRepository(session)
    )
    decision_service = DecisionService(
        DecisionRepository(session)
    )
    audit_event_service = AuditEventService(
        AuditEventRepository(session)
    )

    # The LLM retains dynamic tool selection. It does not receive
    # authority to classify or execute refunds directly.
    try:
        agent_graph = build_claim_agent_graph(
            claim_service=claim_service,
            customer_service=customer_service,
            policy_service=policy_service,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "The agent model or configuration is invalid. "
                "Check CLAIMS_AGENT_MODEL, the local Ollama endpoint, "
                "and the required OpenAI-compatible client settings."
            ),
        ) from exc

    # The faculty classifier is injected into the orchestrator as the
    # authoritative source of classification tier, reasons and clause.
    return AgentRunOrchestrator(
        agent_run_service=agent_run_service,
        claim_service=claim_service,
        customer_service=customer_service,
        decision_service=decision_service,
        audit_event_service=audit_event_service,
        agent_graph=agent_graph,
        claim_classifier=faculty_classify,
    )


@router.post(
    "/{run_id}/execute",
    response_model=AgentRunExecutionResponse,
)
def execute_agent_run(
    run_id: str,
    orchestrator: AgentRunOrchestrator = Depends(
        get_agent_run_orchestrator
    ),
) -> AgentRunExecutionResponse:
    try:
        result = orchestrator.execute(run_id)

    except ValueError as exc:
        message = str(exc)

        if "not found" in message:
            raise HTTPException(
                status_code=404,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=409,
            detail=message,
        ) from exc

    return AgentRunExecutionResponse(
        agent_run=result.agent_run,
        decision=result.decision,
        graph_status=result.graph_status,
        evidence_count=result.evidence_count,
        tool_call_count=result.tool_call_count,
        error_message=result.error_message,
    )
