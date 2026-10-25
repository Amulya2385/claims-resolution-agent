from claims_resolution_agent.application.agent_context import (
    AgentContextAccumulator,
)
from claims_resolution_agent.domain.agent_models import (
    AgentEvidence,
    ReasoningStep,
    ToolCall,
)


class AgentObserver:
    def __init__(self, context: AgentContextAccumulator):
        self.context = context

    def record_tool_call(self, tool_call: ToolCall) -> None:
        self.context.add_tool_call(tool_call)

    def record_evidence(
        self,
        evidence: list[AgentEvidence],
    ) -> None:
        self.context.add_evidence(evidence)

    def record_reasoning_step(
        self,
        reasoning_step: ReasoningStep,
    ) -> None:
        self.context.add_reasoning_step(reasoning_step)

    def record_observation(
        self,
        tool_call: ToolCall,
        evidence: list[AgentEvidence],
    ) -> None:
        self.record_tool_call(tool_call)
        self.record_evidence(evidence)

    def snapshot(self):
        return self.context.snapshot()