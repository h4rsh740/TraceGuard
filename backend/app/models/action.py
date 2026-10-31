"""Action model for human-in-the-loop remediation."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from backend.app.db.base import Base

JSONType = JSON().with_variant(postgresql.JSONB, "postgresql")


class ActionType(enum.StrEnum):
    REFUND = "REFUND"
    DISPUTE_EVIDENCE = "DISPUTE_EVIDENCE"


class ActionStatus(enum.StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"ACT-{uuid.uuid4().hex[:12].upper()}"
    )
    incident_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=ActionStatus.DRAFT.value, nullable=False, index=True
    )

    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # PayPal-Request-Id idempotency key ensuring no double refund can execute
    idempotency_key: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
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
    incident = relationship("Incident", back_populates="actions")

    def __repr__(self) -> str:
        return (
            f"<Action {self.id} incident={self.incident_id} type={self.type} status={self.status}>"
        )
