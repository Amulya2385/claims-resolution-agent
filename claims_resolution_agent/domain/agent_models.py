from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source_type: str
    source_id: str
    content: str
    locator: str | None = None
    relevance: float = Field(
    ge=0,
    description="Source-specific relevance score; not a calibrated probability.",
)


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: dict
    purpose: str


class ReasoningStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    action: str
    observation: str
    evidence_ids: list[str] = Field(default_factory=list)


class AgentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    claim_id: str
    claim: dict
    customer: dict | None = None
    evidence: list[AgentEvidence] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    reasoning_steps: list[ReasoningStep] = Field(default_factory=list)


class DecisionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    run_id: str
    claim_id: str
    recommendation: str
    tier: str
    reasons: list[str] = Field(min_length=1)
    policy_evidence: list[AgentEvidence] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    created_at: datetime