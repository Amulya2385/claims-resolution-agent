from claims_resolution_agent.application.tool_registry import AgentToolRegistry
from claims_resolution_agent.domain.agent_models import (
    AgentContext,
    AgentEvidence,
    ToolCall,
)


class AgentToolExecutor:
    def __init__(self, registry: AgentToolRegistry):
        self.registry = registry

    def execute(
        self,
        tool_call: ToolCall,
        context: AgentContext,
    ) -> list[AgentEvidence]:
        if not tool_call.tool_name.strip():
            raise ValueError("tool name cannot be empty")

        # The registry revalidates both arguments and authorization
        # immediately before calling the underlying application tool.
        result = self.registry.execute(
            tool_call.tool_name,
            context,
            **tool_call.arguments,
        )

        if not isinstance(result, list):
            raise TypeError(
                f"tool '{tool_call.tool_name}' must return "
                "a list of AgentEvidence"
            )

        for evidence in result:
            if not isinstance(evidence, AgentEvidence):
                raise TypeError(
                    f"tool '{tool_call.tool_name}' returned "
                    "an invalid evidence item"
                )

        return result