from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from claims_resolution_agent.domain.agent_models import ToolCall


class ReasoningAction(str, Enum):
    TOOL_CALL = "tool_call"
    PROPOSAL = "proposal"


class ProposalReasoning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: str
    tier: str
    reasons: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class LLMReasoningOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ReasoningAction
    tool_call: ToolCall | None = None
    proposal: ProposalReasoning | None = None

    @model_validator(mode="after")
    def validate_action_payload(self) -> "LLMReasoningOutput":
        if self.action == ReasoningAction.TOOL_CALL:
            if self.tool_call is None:
                raise ValueError(
                    "tool_call is required when action is tool_call"
                )
            if self.proposal is not None:
                raise ValueError(
                    "proposal must be absent when action is tool_call"
                )

        elif self.action == ReasoningAction.PROPOSAL:
            if self.proposal is None:
                raise ValueError(
                    "proposal is required when action is proposal"
                )
            if self.tool_call is not None:
                raise ValueError(
                    "tool_call must be absent when action is proposal"
                )

        return self