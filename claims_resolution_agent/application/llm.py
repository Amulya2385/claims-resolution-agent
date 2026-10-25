from abc import ABC, abstractmethod

from claims_resolution_agent.domain.agent_models import AgentContext
from claims_resolution_agent.domain.reasoning_models import LLMReasoningOutput


class LLMClient(ABC):
    @abstractmethod
    def generate(
        self,
        context: AgentContext,
    ) -> LLMReasoningOutput:
        raise NotImplementedError