from claims_resolution_agent.application.tool_registry import AgentToolRegistry
from claims_resolution_agent.domain.agent_models import AgentContext
from claims_resolution_agent.domain.reasoning_models import (
    LLMReasoningOutput,
    ReasoningAction,
)


class ReasoningOutputValidator:
    def __init__(self, tool_registry: AgentToolRegistry):
        self.tool_registry = tool_registry

    def validate(
        self,
        output: LLMReasoningOutput,
        context: AgentContext,
    ) -> LLMReasoningOutput:
        if output.action == ReasoningAction.TOOL_CALL:
            self._validate_tool_call(output, context)

        elif output.action == ReasoningAction.PROPOSAL:
            self._validate_proposal(output, context)

        else:
            raise ValueError(
                f"unsupported reasoning action: {output.action}"
            )

        return output

    def _validate_tool_call(
        self,
        output: LLMReasoningOutput,
        context: AgentContext,
    ) -> None:
        if output.tool_call is None:
            raise ValueError("tool_call is required")

        tool_name = output.tool_call.tool_name

        if not tool_name.strip():
            raise ValueError("tool name cannot be empty")

        if tool_name != tool_name.strip():
            raise ValueError(
                "tool name cannot contain surrounding whitespace"
            )

        self.tool_registry.validate_arguments(
            tool_name,
            output.tool_call.arguments,
        )

        # Reject unauthorized access before the graph reaches execution.
        self.tool_registry.validate_context(
            tool_name,
            context,
            output.tool_call.arguments,
        )

    @staticmethod
    def _validate_proposal(
        output: LLMReasoningOutput,
        context: AgentContext,
    ) -> None:
        if output.proposal is None:
            raise ValueError("proposal is required")

        if not output.proposal.evidence_ids:
            raise ValueError(
                "proposal must reference at least one evidence item"
            )

        available_evidence_ids = {
            item.evidence_id
            for item in context.evidence
        }

        missing_evidence = [
            evidence_id
            for evidence_id in output.proposal.evidence_ids
            if evidence_id not in available_evidence_ids
        ]

        if missing_evidence:
            raise ValueError(
                "proposal references unavailable evidence: "
                f"{missing_evidence}"
            )