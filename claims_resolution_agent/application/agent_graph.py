from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from claims_resolution_agent.application.agent_context import (
    AgentContextAccumulator,
)
from claims_resolution_agent.application.agent_executor import (
    AgentToolExecutor,
)
from claims_resolution_agent.application.agent_observer import AgentObserver
from claims_resolution_agent.application.reasoning import ReasoningEngine
from claims_resolution_agent.application.reasoning_validator import (
    ReasoningOutputValidator,
)
from claims_resolution_agent.domain.agent_models import (
    AgentContext,
    ReasoningStep,
)
from claims_resolution_agent.domain.reasoning_models import (
    LLMReasoningOutput,
    ProposalReasoning,
    ReasoningAction,
)


GraphStatus = Literal[
    "running",
    "completed",
    "failed",
    "limit_reached",
]


class AgentGraphState(TypedDict):
    context: AgentContext
    reasoning_output: LLMReasoningOutput | None
    proposal: ProposalReasoning | None
    status: GraphStatus
    error: str | None
    iteration_count: int
    tool_call_count: int


class AgentGraph:
    """Controlled single-agent LangGraph runtime."""

    # These markers identify explicit claims about customer refund
    # history. This is a deterministic safeguard for known factual
    # dependencies, not a general semantic fact-verification system.
    _CUSTOMER_HISTORY_MARKERS = (
        "refund history",
        "refund-history",
        "prior refund",
        "previous refund",
        "past refund",
        "approved refunds",
        "approved_refunds_trailing_90d",
        "customer history",
        "customer-history",
        "customer account",
        "account standing",
        "account-standing",
        "refund count",
        "refunds in the trailing 90 days",
        "refunds in the last 90 days",
        "refunds in 90 days",
        "90-day refund",
        "90 days",
        "trailing 90 days",
        "last three months",
    )

    def __init__(
        self,
        reasoning_engine: ReasoningEngine,
        output_validator: ReasoningOutputValidator,
        tool_executor: AgentToolExecutor,
        max_iterations: int = 8,
        max_tool_calls: int = 8,
    ):
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")

        if max_tool_calls < 1:
            raise ValueError("max_tool_calls must be at least 1")

        self.reasoning_engine = reasoning_engine
        self.output_validator = output_validator
        self.tool_executor = tool_executor
        self.max_iterations = max_iterations
        self.max_tool_calls = max_tool_calls

        builder = StateGraph(AgentGraphState)

        builder.add_node("reason", self._reasoning_node)
        builder.add_node("validate", self._validation_node)
        builder.add_node("execute_tool", self._tool_execution_node)
        builder.add_node("finalize", self._finalize_node)
        builder.add_node("limit", self._limit_node)

        builder.add_edge(START, "reason")

        builder.add_conditional_edges(
            "reason",
            self._route_after_reasoning,
            {
                "validate": "validate",
                "end": END,
            },
        )

        builder.add_conditional_edges(
            "validate",
            self._route_after_validation,
            {
                "reason": "reason",
                "execute_tool": "execute_tool",
                "finalize": "finalize",
                "limit": "limit",
                "end": END,
            },
        )

        builder.add_edge("execute_tool", "reason")
        builder.add_edge("finalize", END)
        builder.add_edge("limit", END)

        self._graph = builder.compile()

    def invoke(self, context: AgentContext) -> AgentGraphState:
        initial_state: AgentGraphState = {
            "context": context.model_copy(deep=True),
            "reasoning_output": None,
            "proposal": None,
            "status": "running",
            "error": None,
            "iteration_count": 0,
            "tool_call_count": 0,
        }

        recursion_limit = max(
            25,
            (self.max_iterations * 4) + 10,
        )

        return self._graph.invoke(
            initial_state,
            config={"recursion_limit": recursion_limit},
        )

    @staticmethod
    def _append_step(
        context: AgentContext,
        step: ReasoningStep,
    ) -> AgentContext:
        accumulator = AgentContextAccumulator(context)
        observer = AgentObserver(accumulator)
        observer.record_reasoning_step(step)
        return observer.snapshot()

    @classmethod
    def _proposal_requires_customer_evidence(
        cls,
        proposal: ProposalReasoning,
    ) -> bool:
        """Identify proposal rationales explicitly dependent on customer history."""
        text = " ".join(
            [
                proposal.recommendation,
                *proposal.reasons,
            ]
        ).casefold()

        return any(
            marker in text
            for marker in cls._CUSTOMER_HISTORY_MARKERS
        )

    def _reasoning_node(
        self,
        state: AgentGraphState,
    ) -> dict:
        iteration = state["iteration_count"] + 1
        context = state["context"].model_copy(deep=True)

        try:
            output = self.reasoning_engine.reason(context)

            if not isinstance(output, LLMReasoningOutput):
                raise TypeError(
                    "ReasoningEngine must return LLMReasoningOutput"
                )

        except Exception as exc:
            context = self._append_step(
                context,
                ReasoningStep(
                    step_id=(
                        f"{context.run_id}:reason:{iteration}:failed"
                    ),
                    action="reasoning_failed",
                    observation=(
                        f"Reasoning failed ({type(exc).__name__}). "
                        "No proposal was accepted."
                    ),
                    evidence_ids=[],
                ),
            )

            return {
                "context": context,
                "reasoning_output": None,
                "proposal": None,
                "status": "failed",
                "error": (
                    f"Reasoning engine failed ({type(exc).__name__})."
                ),
                "iteration_count": iteration,
            }

        return {
            "reasoning_output": output,
            "proposal": None,
            "status": "running",
            "error": None,
            "iteration_count": iteration,
        }

    @staticmethod
    def _route_after_reasoning(
        state: AgentGraphState,
    ) -> Literal["validate", "end"]:
        if state["status"] != "running":
            return "end"

        return "validate"

    def _validation_node(
        self,
        state: AgentGraphState,
    ) -> dict:
        output = state["reasoning_output"]

        if output is None:
            return {
                "status": "failed",
                "error": (
                    "No reasoning output was available for validation."
                ),
                "proposal": None,
            }

        context = state["context"].model_copy(deep=True)

        try:
            self.output_validator.validate(output, context)

        except Exception as exc:
            context = self._append_step(
                context,
                ReasoningStep(
                    step_id=(
                        f"{context.run_id}:validate:"
                        f"{state['iteration_count']}:failed"
                    ),
                    action="validation_failed",
                    observation=(
                        "The proposed action failed validation "
                        "and was rejected. No tool was executed "
                        "and no proposal was accepted."
                    ),
                    evidence_ids=[],
                ),
            )

            return {
                "context": context,
                "reasoning_output": None,
                "proposal": None,
                "status": "failed",
                "error": (
                    "Reasoning output validation failed "
                    f"({type(exc).__name__})."
                ),
            }

        if output.action != ReasoningAction.PROPOSAL:
            return {
                "status": "running",
                "error": None,
            }

        proposal = output.proposal

        if proposal is None:
            return {
                "status": "failed",
                "error": "No proposal payload was available.",
                "proposal": None,
            }

        evidence_by_id = {
            item.evidence_id: item
            for item in context.evidence
        }

        # The output validator must reject unknown evidence IDs before
        # this point, so the cited evidence can now be safely resolved.
        referenced_evidence = [
            evidence_by_id[evidence_id]
            for evidence_id in proposal.evidence_ids
        ]

        # Gate 1: a claim decision proposal must cite retrieved policy
        # evidence rather than merely asserting that policy supports it.
        has_policy_evidence = any(
            item.source_type == "policy"
            for item in referenced_evidence
        )

        if not has_policy_evidence:
            context = self._append_step(
                context,
                ReasoningStep(
                    step_id=(
                        f"{context.run_id}:validate:"
                        f"{state['iteration_count']}:policy_required"
                    ),
                    action=(
                        "proposal_rejected_insufficient_policy_evidence"
                    ),
                    observation=(
                        "The proposal was not accepted because its "
                        "referenced evidence contains no retrieved "
                        "policy evidence. Continue investigating using "
                        "an appropriate approved action. Do not invent "
                        "policy clauses, evidence, or tool results."
                    ),
                    evidence_ids=[],
                ),
            )

            return {
                "context": context,
                "reasoning_output": None,
                "proposal": None,
                "status": "running",
                "error": None,
            }

        # Gate 2: if the rationale makes an explicit customer-history
        # claim, the proposal must cite retrieved customer evidence.
        #
        # We do not prescribe the tool order. The LLM chooses the next
        # action after receiving this validation feedback.
        if self._proposal_requires_customer_evidence(proposal):
            has_referenced_customer_evidence = any(
                item.source_type == "customer"
                for item in referenced_evidence
            )

            if not has_referenced_customer_evidence:
                context = self._append_step(
                    context,
                    ReasoningStep(
                        step_id=(
                            f"{context.run_id}:validate:"
                            f"{state['iteration_count']}:"
                            "customer_evidence_required"
                        ),
                        action=(
                            "proposal_rejected_insufficient_customer_evidence"
                        ),
                        observation=(
                            "The proposal makes a claim about customer "
                            "or refund history but does not cite retrieved "
                            "customer evidence. Retrieve the relevant "
                            "customer information using an appropriate "
                            "approved action, or remove the unsupported "
                            "claim from the rationale. Do not invent "
                            "customer history or infer missing data."
                        ),
                        evidence_ids=[],
                    ),
                )

                return {
                    "context": context,
                    "reasoning_output": None,
                    "proposal": None,
                    "status": "running",
                    "error": None,
                }

        return {
            "status": "running",
            "error": None,
        }

    def _route_after_validation(
        self,
        state: AgentGraphState,
    ) -> Literal[
        "reason",
        "execute_tool",
        "finalize",
        "limit",
        "end",
    ]:
        if state["status"] != "running":
            return "end"

        output = state["reasoning_output"]

        # A rejected proposal has its output cleared. Let the model
        # choose its next action, but enforce the configured budgets.
        if output is None:
            if state["iteration_count"] >= self.max_iterations:
                return "limit"

            if state["tool_call_count"] >= self.max_tool_calls:
                return "limit"

            return "reason"

        if output.action == ReasoningAction.PROPOSAL:
            return "finalize"

        if state["iteration_count"] >= self.max_iterations:
            return "limit"

        if state["tool_call_count"] >= self.max_tool_calls:
            return "limit"

        if output.action == ReasoningAction.TOOL_CALL:
            return "execute_tool"

        return "end"

    def _tool_execution_node(
        self,
        state: AgentGraphState,
    ) -> dict:
        output = state["reasoning_output"]
        context = state["context"].model_copy(deep=True)

        if output is None or output.tool_call is None:
            return {
                "status": "failed",
                "error": (
                    "No validated tool call was available for execution."
                ),
                "proposal": None,
            }

        tool_call = output.tool_call
        attempt = state["tool_call_count"] + 1

        observer = AgentObserver(
            AgentContextAccumulator(context)
        )

        observer.record_tool_call(tool_call)

        try:
            evidence = self.tool_executor.execute(
                tool_call,
                context=context,
            )

        except Exception as exc:
            observer.record_reasoning_step(
                ReasoningStep(
                    step_id=(
                        f"{context.run_id}:tool:{attempt}:failed"
                    ),
                    action="tool_call_failed",
                    observation=(
                        f"Tool '{tool_call.tool_name}' failed "
                        f"({type(exc).__name__}). No result was accepted. "
                        "The agent may investigate another way or stop "
                        "if the available evidence is sufficient."
                    ),
                    evidence_ids=[],
                )
            )

            return {
                "context": observer.snapshot(),
                "reasoning_output": None,
                "proposal": None,
                "status": "running",
                "error": None,
                "tool_call_count": attempt,
            }

        observer.record_evidence(evidence)

        observer.record_reasoning_step(
            ReasoningStep(
                step_id=(
                    f"{context.run_id}:tool:{attempt}:completed"
                ),
                action="tool_call_completed",
                observation=(
                    f"Tool '{tool_call.tool_name}' completed and "
                    f"returned {len(evidence)} evidence item(s)."
                ),
                evidence_ids=[
                    item.evidence_id
                    for item in evidence
                ],
            )
        )

        return {
            "context": observer.snapshot(),
            "reasoning_output": None,
            "proposal": None,
            "status": "running",
            "error": None,
            "tool_call_count": attempt,
        }

    def _finalize_node(
        self,
        state: AgentGraphState,
    ) -> dict:
        output = state["reasoning_output"]

        if output is None or output.proposal is None:
            return {
                "status": "failed",
                "error": (
                    "No validated proposal was available to finalize."
                ),
                "proposal": None,
            }

        context = state["context"].model_copy(deep=True)
        proposal = output.proposal

        context = self._append_step(
            context,
            ReasoningStep(
                step_id=(
                    f"{context.run_id}:proposal:"
                    f"{state['iteration_count']}:created"
                ),
                action="proposal_created",
                observation=(
                    "An evidence-referenced decision proposal was "
                    "validated. No claim approval or financial action "
                    "was executed."
                ),
                evidence_ids=proposal.evidence_ids,
            ),
        )

        return {
            "context": context,
            "proposal": proposal,
            "status": "completed",
            "error": None,
        }

    def _limit_node(
        self,
        state: AgentGraphState,
    ) -> dict:
        context = state["context"].model_copy(deep=True)

        if state["iteration_count"] >= self.max_iterations:
            message = (
                "Maximum reasoning iterations reached before a "
                "valid evidence-grounded proposal was produced."
            )
        else:
            message = (
                "Maximum tool-call budget exhausted before a "
                "valid evidence-grounded proposal was produced."
            )

        context = self._append_step(
            context,
            ReasoningStep(
                step_id=(
                    f"{context.run_id}:limit:"
                    f"{state['iteration_count']}:reached"
                ),
                action="limit_reached",
                observation=message,
                evidence_ids=[],
            ),
        )

        return {
            "context": context,
            "proposal": None,
            "status": "limit_reached",
            "error": message,
        }