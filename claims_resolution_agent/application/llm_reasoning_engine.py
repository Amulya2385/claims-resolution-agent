from claims_resolution_agent.application.llm import LLMClient
from claims_resolution_agent.application.reasoning import ReasoningEngine
from claims_resolution_agent.domain.agent_models import AgentContext
from claims_resolution_agent.domain.reasoning_models import LLMReasoningOutput


class LLMReasoningEngine(ReasoningEngine):
    """Delegates agent reasoning to a configured LLM client."""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def reason(self, context: AgentContext) -> LLMReasoningOutput:
        output = self.llm_client.generate(context)

        if not isinstance(output, LLMReasoningOutput):
            raise TypeError(
                "LLMClient.generate() must return LLMReasoningOutput"
            )

        return output