from abc import ABC, abstractmethod

from claims_resolution_agent.domain.agent_models import AgentContext
from claims_resolution_agent.domain.reasoning_models import LLMReasoningOutput


class ReasoningEngine(ABC):
    @abstractmethod
    def reason(self, context: AgentContext) -> LLMReasoningOutput:
        raise NotImplementedError