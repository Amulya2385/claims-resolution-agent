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