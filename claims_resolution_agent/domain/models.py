from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClaimData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    order_id: str
    customer_id: str
    amount: float = Field(gt=0)
    currency: str
    reason: str
    photo_on_file: bool = False
    chargeback_in_progress: bool = False
    customer_description: str | None = None


class ClassificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: str
    reasons: list[str]
    policy_clause: str


class ApprovalSignatureData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approver_id: str
    signed_at: datetime


class ApprovalData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str
    claim_id: str
    payload_hash: str
    required_approvers: int = Field(ge=0)
    signatures: list[ApprovalSignatureData] = Field(default_factory=list)
    created_at: datetime
    expires_at: datetime
    status: str


class BoundaryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: str
    required_approvers: int | None
    max_amount: float | None


class RefundExecutionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    idempotency_key: str
    amount: float = Field(gt=0)
    currency: str
    tier: str
    status: str
    entry_hash: str | None = None
    executed_at: datetime


class CustomerData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str
    approved_refunds_trailing_90d: int = Field(ge=0)


class PolicySearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    locator: str
    heading: str
    text: str
    rrf_score: float


class AgentRunData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    claim_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


class DecisionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    run_id: str
    claim_id: str
    tier: str
    recommendation: str
    reasons: list[str]
    policy_clause: str
    status: str
    created_at: datetime


class AuditEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    claim_id: str
    run_id: str | None = None
    event_type: str
    actor_type: str
    actor_id: str | None = None
    payload: dict


class AuditEventData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    claim_id: str
    run_id: str | None = None
    event_type: str
    actor_type: str
    actor_id: str | None = None
    payload: dict
    created_at: datetime


class EvaluationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    run_id: str | None = None
    evaluation_type: str
    accuracy: float = Field(ge=0, le=1)
    accuracy_floor: float = Field(ge=0, le=1)
    passed: bool
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    results: list[dict]


class EvaluationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    run_id: str | None = None
    evaluation_type: str
    accuracy: float = Field(ge=0, le=1)
    accuracy_floor: float = Field(ge=0, le=1)
    passed: bool
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    results: list[dict]
    created_at: datetime