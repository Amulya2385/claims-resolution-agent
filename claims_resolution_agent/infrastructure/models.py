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