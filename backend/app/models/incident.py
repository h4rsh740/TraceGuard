"""Incident model for deterministic detection of payment anomalies."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class IncidentType(enum.StrEnum):
    DUPLICATE_PAYMENT = "DUPLICATE_PAYMENT"
    REFUND_MISMATCH = "REFUND_MISMATCH"
    DISPUTE_ITEM_NOT_RECEIVED = "DISPUTE_ITEM_NOT_RECEIVED"


class IncidentStatus(enum.StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    AWAITING_APPROVAL = "awaiting_approval"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"INC-{uuid.uuid4().hex[:12].upper()}"
    )
    order_ref: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=IncidentStatus.OPEN.value, nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    actions = relationship("Action", back_populates="incident", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="incident", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_incidents_order_type", "order_ref", "type"),)

    def __repr__(self) -> str:
        return f"<Incident {self.id} order={self.order_ref} type={self.type} status={self.status}>"
