
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from claims_resolution_agent.api.main import app
from claims_resolution_agent.api.routes.agent_execution import (
    get_agent_run_orchestrator,
)
from claims_resolution_agent.application.agent_run_orchestrator import (
    AgentRunExecutionResult,
)
from claims_resolution_agent.domain.models import (
    AgentRunData,
    DecisionData,
)


RUN_ID = "RUN-API-001"
CLAIM_ID = "CLM-API-001"


def build_success_result() -> AgentRunExecutionResult:
    now = datetime.now(timezone.utc)

    return AgentRunExecutionResult(
        agent_run=AgentRunData(
            run_id=RUN_ID,
            claim_id=CLAIM_ID,
            status="completed",
            started_at=now,
            completed_at=now,
        ),
        decision=DecisionData(
            decision_id="dec-api-001",
            run_id=RUN_ID,
            claim_id=CLAIM_ID,
            tier="review",
            recommendation="manual_review",
            reasons=["The evidence requires human review."],
            policy_clause="POL-001:section-2",
            status="proposed",
            created_at=now,
        ),
        graph_status="completed",
        evidence_count=3,
        tool_call_count=2,
    )


def build_failure_result() -> AgentRunExecutionResult:
    now = datetime.now(timezone.utc)

    return AgentRunExecutionResult(
        agent_run=AgentRunData(
            run_id=RUN_ID,
            claim_id=CLAIM_ID,
            status="failed",
            started_at=now,
            completed_at=now,
            error_message="Synthetic reasoning failure.",
        ),
        decision=None,
        graph_status="failed",
        evidence_count=1,
        tool_call_count=0,
        error_message="Synthetic reasoning failure.",
    )


class FakeOrchestrator:
    def __init__(
        self,
        result: AgentRunExecutionResult | None = None,
        error: Exception | None = None,
    ):
        self.result = result or build_success_result()
        self.error = error
        self.executed_run_ids: list[str] = []

    def execute(self, run_id: str) -> AgentRunExecutionResult:
        self.executed_run_ids.append(run_id)

        if self.error is not None:
            raise self.error

        return self.result


@pytest.fixture
def api_client():
    previous_overrides = app.dependency_overrides.copy()

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def override_orchestrator(orchestrator: FakeOrchestrator) -> None:
    app.dependency_overrides[get_agent_run_orchestrator] = (
        lambda: orchestrator
    )


def test_execute_agent_run_returns_proposed_decision(api_client):
    orchestrator = FakeOrchestrator()
    override_orchestrator(orchestrator)

    response = api_client.post(
        f"/api/v1/agent-runs/{RUN_ID}/execute"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["agent_run"]["run_id"] == RUN_ID
    assert body["agent_run"]["status"] == "completed"
    assert body["graph_status"] == "completed"

    assert body["decision"]["status"] == "proposed"
    assert body["decision"]["recommendation"] == "manual_review"
    assert body["decision"]["policy_clause"] == "POL-001:section-2"

    assert body["evidence_count"] == 3
    assert body["tool_call_count"] == 2
    assert body["error_message"] is None

    assert orchestrator.executed_run_ids == [RUN_ID]


def test_execute_agent_run_returns_failed_execution(api_client):
    orchestrator = FakeOrchestrator(
        result=build_failure_result()
    )
    override_orchestrator(orchestrator)

    response = api_client.post(
        f"/api/v1/agent-runs/{RUN_ID}/execute"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["agent_run"]["status"] == "failed"
    assert body["graph_status"] == "failed"
    assert body["decision"] is None
    assert body["error_message"] == "Synthetic reasoning failure."


def test_execute_agent_run_returns_404_for_missing_run(api_client):
    orchestrator = FakeOrchestrator(
        error=ValueError(f"agent run not found: {RUN_ID}")
    )
    override_orchestrator(orchestrator)

    response = api_client.post(
        f"/api/v1/agent-runs/{RUN_ID}/execute"
    )

    assert response.status_code == 404
    assert "agent run not found" in response.json()["detail"]


def test_execute_agent_run_returns_409_for_invalid_run_state(api_client):
    orchestrator = FakeOrchestrator(
        error=ValueError(
            f"agent run '{RUN_ID}' cannot be executed from "
            "status 'completed'"
        )
    )
    override_orchestrator(orchestrator)

    response = api_client.post(
        f"/api/v1/agent-runs/{RUN_ID}/execute"
    )

    assert response.status_code == 409
    assert "cannot be executed from status" in (
        response.json()["detail"]
    )


def test_execute_agent_run_propagates_configuration_unavailable(api_client):
    def unavailable_dependency():
        raise HTTPException(
            status_code=503,
            detail="The agent model is not configured.",
        )

    app.dependency_overrides[
        get_agent_run_orchestrator
    ] = unavailable_dependency

    response = api_client.post(
        f"/api/v1/agent-runs/{RUN_ID}/execute"
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "The agent model is not configured."
    )
