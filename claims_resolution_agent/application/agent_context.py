from claims_resolution_agent.domain.agent_models import (
    AgentContext,
    AgentEvidence,
    ReasoningStep,
    ToolCall,
)


class AgentContextAccumulator:
    def __init__(self, context: AgentContext):
        self.context = context

    def add_evidence(
        self,
        evidence: list[AgentEvidence],
    ) -> None:
        existing_ids = {
            item.evidence_id
            for item in self.context.evidence
        }

        for item in evidence:
            if item.evidence_id not in existing_ids:
                self.context.evidence.append(item)
                existing_ids.add(item.evidence_id)

    def add_tool_call(
        self,
        tool_call: ToolCall,
    ) -> None:
        self.context.tool_calls.append(tool_call)

    def add_reasoning_step(
        self,
        reasoning_step: ReasoningStep,
    ) -> None:
        self.context.reasoning_steps.append(reasoning_step)

    def get_evidence(self) -> list[AgentEvidence]:
        return list(self.context.evidence)

    def get_tool_calls(self) -> list[ToolCall]:
        return list(self.context.tool_calls)

    def get_reasoning_steps(self) -> list[ReasoningStep]:
        return list(self.context.reasoning_steps)

    def snapshot(self) -> AgentContext:
        return self.context.model_copy(deep=True)