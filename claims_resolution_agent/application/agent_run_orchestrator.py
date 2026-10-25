from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from claims_resolution_agent.application.agent_graph import AgentGraph
from claims_resolution_agent.application.services.agent_runs import AgentRunService
from claims_resolution_agent.application.services.audit_events import AuditEventService
from claims_resolution_agent.application.services.claims import ClaimService
from claims_resolution_agent.application.services.customers import CustomerService
from claims_resolution_agent.application.services.decisions import DecisionService
from claims_resolution_agent.domain.agent_models import AgentContext, AgentEvidence
from claims_resolution_agent.domain.models import AgentRunData, DecisionData
from claims_resolution_agent.server.classification import (
    TIER_DECLINE,
    TIER_FOUR_EYES,
    TIER_ROUTINE,
    TIER_SINGLE_APPROVAL,
)


ClaimClassifier = Callable[[dict, int], dict]

ALLOWED_TIERS = {
    TIER_ROUTINE,
    TIER_SINGLE_APPROVAL,
    TIER_FOUR_EYES,
    TIER_DECLINE,
}


@dataclass(frozen=True)
class AgentRunExecutionResult:
    agent_run: AgentRunData
    decision: DecisionData | None
    graph_status: str
    evidence_count: int
    tool_call_count: int
    error_message: str | None = None


class AgentRunOrchestrator:
    """Coordinate dynamic agent execution with post-investigation governance."""

    def __init__(
        self,
        agent_run_service: AgentRunService,
        claim_service: ClaimService,
        customer_service: CustomerService,
        decision_service: DecisionService,
        audit_event_service: AuditEventService,
        agent_graph: AgentGraph,
        claim_classifier: ClaimClassifier,
    ):
        self.agent_run_service = agent_run_service
        self.claim_service = claim_service
        self.customer_service = customer_service
        self.decision_service = decision_service
        self.audit_event_service = audit_event_service
        self.agent_graph = agent_graph
        self.claim_classifier = claim_classifier

    def execute(self, run_id: str) -> AgentRunExecutionResult:
        run = self.agent_run_service.get_agent_run(run_id)

        if run is None:
            raise ValueError(f"agent run not found: {run_id}")

        if run.status != "started":
            raise ValueError(
                f"agent run '{run_id}' cannot be executed from "
                f"status '{run.status}'"
            )

        claim = self.claim_service.get_claim(run.claim_id)

        if claim is None:
            return self._fail(
                run=run,
                graph_status="failed",
                error_message=(
                    "The claim associated with this agent run "
                    "could not be retrieved."
                ),
                evidence=[],
                tool_call_count=0,
            )

        initial_evidence = AgentEvidence(
            evidence_id=f"claim:{claim.claim_id}",
            source_type="claim",
            source_id=claim.claim_id,
            content=claim.model_dump_json(),
            locator=f"claim:{claim.claim_id}",
            relevance=1.0,
        )

        context = AgentContext(
            run_id=run.run_id,
            claim_id=run.claim_id,
            claim=claim.model_dump(mode="json"),
            evidence=[initial_evidence],
        )

        self._write_audit_event(
            run=run,
            event_type="agent_execution_started",
            payload={
                "status": "started",
                "initial_evidence_ids": [initial_evidence.evidence_id],
                "execution_authority": "proposal_only",
            },
        )

        # The LLM owns investigation choices. No customer or policy
        # tool is called here by a predetermined orchestration sequence.
        try:
            graph_result = self.agent_graph.invoke(context)
        except Exception as exc:
            return self._fail(
                run=run,
                graph_status="failed",
                error_message=(
                    "Agent graph execution failed "
                    f"({type(exc).__name__})."
                ),
                evidence=[initial_evidence],
                tool_call_count=0,
            )

        final_context = graph_result["context"]
        proposal = graph_result.get("proposal")
        tool_call_count = graph_result["tool_call_count"]
        graph_status = graph_result["status"]
        evidence = final_context.evidence

        if graph_status != "completed" or proposal is None:
            return self._fail(
                run=run,
                graph_status=graph_status,
                error_message=(
                    graph_result.get("error")
                    or "Agent execution ended without a valid proposal."
                ),
                evidence=evidence,
                tool_call_count=tool_call_count,
            )

        evidence_by_id = {
            item.evidence_id: item
            for item in evidence
        }

        missing_evidence = [
            evidence_id
            for evidence_id in proposal.evidence_ids
            if evidence_id not in evidence_by_id
        ]

        if missing_evidence:
            return self._fail(
                run=run,
                graph_status="proposal_rejected",
                error_message=(
                    "Proposal references unavailable evidence: "
                    f"{missing_evidence}"
                ),
                evidence=evidence,
                tool_call_count=tool_call_count,
            )

        referenced_policy_evidence = [
            evidence_by_id[evidence_id]
            for evidence_id in proposal.evidence_ids
            if evidence_by_id[evidence_id].source_type == "policy"
        ]

        if not referenced_policy_evidence:
            return self._fail(
                run=run,
                graph_status="proposal_rejected",
                error_message=(
                    "The proposal does not reference retrieved policy "
                    "evidence. It cannot be persisted under the current "
                    "Decision schema."
                ),
                evidence=evidence,
                tool_call_count=tool_call_count,
            )

        # Governance begins after investigation. It uses the existing
        # customer service and the faculty-provided classifier.
        try:
            customer = self.customer_service.get_customer(
                claim.customer_id
            )

            if customer is None:
                return self._fail(
                    run=run,
                    graph_status="classification_failed",
                    error_message=(
                        "The customer history required by the faculty "
                        "classifier could not be retrieved. "
                        "Classification failed closed."
                    ),
                    evidence=evidence,
                    tool_call_count=tool_call_count,
                )

            classification = self.claim_classifier(
                claim.model_dump(mode="json"),
                customer.approved_refunds_trailing_90d,
            )

            self._validate_classification(classification)

        except Exception as exc:
            return self._fail(
                run=run,
                graph_status="classification_failed",
                error_message=(
                    "Authoritative faculty classification failed "
                    f"({type(exc).__name__})."
                ),
                evidence=evidence,
                tool_call_count=tool_call_count,
            )

        authoritative_policy_clause = classification["policy_clause"]
        expected_policy_document = authoritative_policy_clause.split(
            "#", 1
        )[0]

        matching_policy_evidence = [
            item
            for item in referenced_policy_evidence
            if (
                item.source_id == expected_policy_document
                and item.locator == authoritative_policy_clause
            )
        ]

        if not matching_policy_evidence:
            return self._fail(
                run=run,
                graph_status="proposal_rejected",
                error_message=(
                    "The proposal does not reference the exact policy "
                    "clause required by the faculty classification: "
                    f"{authoritative_policy_clause}"
                ),
                evidence=evidence,
                tool_call_count=tool_call_count,
            )

        recommendation = proposal.recommendation.strip()

        if not recommendation or len(recommendation) > 64:
            return self._fail(
                run=run,
                graph_status="proposal_rejected",
                error_message=(
                    "Proposal recommendation is empty or exceeds the "
                    "Decision schema's 64-character limit."
                ),
                evidence=evidence,
                tool_call_count=tool_call_count,
            )

        authoritative_tier = classification["tier"]

        decision_reasons = list(
            dict.fromkeys(
                [
                    *classification["reasons"],
                    *proposal.reasons,
                ]
            )
        )

        decision_id = f"dec_{uuid4().hex}"

        try:
            decision = self.decision_service.create_decision(
                decision_id=decision_id,
                run_id=run.run_id,
                claim_id=run.claim_id,
                tier=authoritative_tier,
                recommendation=recommendation,
                reasons=decision_reasons,
                policy_clause=authoritative_policy_clause,
                status="proposed",
            )

            self._write_audit_event(
                run=run,
                event_type="agent_proposal_created",
                payload={
                    "decision_id": decision.decision_id,
                    "decision_status": decision.status,
                    "recommendation": recommendation,
                    "model_proposed_tier": proposal.tier,
                    "authoritative_tier": authoritative_tier,
                    "classification_reasons": classification["reasons"],
                    "classification_policy_clause": (
                        authoritative_policy_clause
                    ),
                    "classification_customer_id": customer.customer_id,
                    "approved_refunds_trailing_90d": (
                        customer.approved_refunds_trailing_90d
                    ),
                    "reasons": decision_reasons,
                    "confidence": proposal.confidence,
                    "confidence_semantics": (
                        "uncalibrated model assessment"
                    ),
                    "evidence_references": [
                        self._evidence_reference(item)
                        for item in evidence
                    ],
                    "referenced_evidence_ids": proposal.evidence_ids,
                    "tool_calls": [
                        {
                            "tool_name": call.tool_name,
                            "purpose": call.purpose,
                        }
                        for call in final_context.tool_calls
                    ],
                    "reasoning_steps": [
                        {
                            "step_id": step.step_id,
                            "action": step.action,
                            "evidence_ids": step.evidence_ids,
                        }
                        for step in final_context.reasoning_steps
                    ],
                    "execution_authority": "proposal_only",
                },
            )

            updated_run = self.agent_run_service.update_status(
                run_id=run.run_id,
                status="completed",
            )

        except Exception as exc:
            return self._fail(
                run=run,
                graph_status="persistence_failed",
                error_message=(
                    "Agent proposal persistence or finalization failed "
                    f"({type(exc).__name__})."
                ),
                evidence=evidence,
                tool_call_count=tool_call_count,
            )

        return AgentRunExecutionResult(
            agent_run=updated_run,
            decision=decision,
            graph_status="completed",
            evidence_count=len(evidence),
            tool_call_count=tool_call_count,
        )

    @staticmethod
    def _validate_classification(classification: dict) -> None:
        if not isinstance(classification, dict):
            raise ValueError("Faculty classifier must return an object.")

        tier = classification.get("tier")
        reasons = classification.get("reasons")
        policy_clause = classification.get("policy_clause")

        if tier not in ALLOWED_TIERS:
            raise ValueError(
                "Faculty classifier returned an unsupported tier."
            )

        if (
            not isinstance(reasons, list)
            or not reasons
            or not all(
                isinstance(reason, str) and reason.strip()
                for reason in reasons
            )
        ):
            raise ValueError(
                "Faculty classifier returned invalid reasons."
            )

        if (
            not isinstance(policy_clause, str)
            or not policy_clause.strip()
            or "#" not in policy_clause
        ):
            raise ValueError(
                "Faculty classifier returned an invalid policy clause."
            )

    def _fail(
        self,
        run: AgentRunData,
        graph_status: str,
        error_message: str,
        evidence: list[AgentEvidence],
        tool_call_count: int,
    ) -> AgentRunExecutionResult:
        updated_run = self.agent_run_service.update_status(
            run_id=run.run_id,
            status="failed",
            error_message=error_message,
        )

        self._write_audit_event(
            run=run,
            event_type="agent_execution_failed",
            payload={
                "graph_status": graph_status,
                "error": error_message,
                "evidence_references": [
                    self._evidence_reference(item)
                    for item in evidence
                ],
                "evidence_count": len(evidence),
                "tool_call_count": tool_call_count,
                "execution_authority": "proposal_only",
            },
        )

        return AgentRunExecutionResult(
            agent_run=updated_run,
            decision=None,
            graph_status=graph_status,
            evidence_count=len(evidence),
            tool_call_count=tool_call_count,
            error_message=error_message,
        )

    def _write_audit_event(
        self,
        run: AgentRunData,
        event_type: str,
        payload: dict,
    ) -> None:
        self.audit_event_service.create_event(
            event_id=f"audit_{uuid4().hex}",
            claim_id=run.claim_id,
            run_id=run.run_id,
            event_type=event_type,
            actor_type="agent",
            actor_id="claims-resolution-agent",
            payload=payload,
        )

    @staticmethod
    def _evidence_reference(evidence: AgentEvidence) -> dict:
        return {
            "evidence_id": evidence.evidence_id,
            "source_type": evidence.source_type,
            "source_id": evidence.source_id,
            "locator": evidence.locator,
        }