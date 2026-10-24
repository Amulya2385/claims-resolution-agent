from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Claim(Base):
    __tablename__ = "claims"

    claim_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    photo_on_file: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    chargeback_in_progress: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    customer_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    approvals: Mapped[list["ApprovalRecord"]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
    )

    executions: Mapped[list["RefundExecution"]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
    )


class ApprovalRecord(Base):
    __tablename__ = "approval_records"

    approval_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("claims.claim_id"),
        nullable=False,
        index=True,
    )
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    required_approvers: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    claim: Mapped["Claim"] = relationship(back_populates="approvals")

    signatures: Mapped[list["ApprovalSignature"]] = relationship(
        back_populates="approval",
        cascade="all, delete-orphan",
    )


class ApprovalSignature(Base):
    __tablename__ = "approval_signatures"

    __table_args__ = (
        UniqueConstraint(
            "approval_id",
            "approver_id",
            name="uq_approval_signature_approver",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    approval_id: Mapped[str] = mapped_column(
        ForeignKey("approval_records.approval_id"),
        nullable=False,
        index=True,
    )
    approver_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    signed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    approval: Mapped["ApprovalRecord"] = relationship(
        back_populates="signatures",
    )


class RefundExecution(Base):
    __tablename__ = "refund_executions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("claims.claim_id"),
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
    )
    amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    tier: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    entry_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    claim: Mapped["Claim"] = relationship(
        back_populates="executions",
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    __table_args__ = (
        Index(
            "ix_ledger_entries_tenant_seq",
            "tenant_id",
            "seq",
        ),
    )

    seq: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    payload: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    prev_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    entry_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    written_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    approved_refunds_trailing_90d: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"

    run_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("claims.claim_id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    claim: Mapped["Claim"] = relationship()


class Decision(Base):
    __tablename__ = "decisions"

    decision_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.run_id"),
        nullable=False,
        index=True,
    )
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("claims.claim_id"),
        nullable=False,
        index=True,
    )
    tier: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    recommendation: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    reasons: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    policy_clause: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("claims.claim_id"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_runs.run_id"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    actor_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    actor_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    payload: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class Evaluation(Base):
    __tablename__ = "evaluations"

    evaluation_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("claims.claim_id"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_runs.run_id"),
        nullable=True,
        index=True,
    )
    evaluator_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    metric: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    details: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )