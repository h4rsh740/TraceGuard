"""AgentRun model for auditing LLM reasoning steps, tool calls, and token usage."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from backend.app.db.base import Base

JSONType = JSON().with_variant(postgresql.JSONB, "postgresql")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"RUN-{uuid.uuid4().hex[:12].upper()}"
    )
    incident_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    model: Mapped[str] = mapped_column(String(128), nullable=False)

    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)
    tokens_used: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    claims: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    validation_errors: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    incident = relationship("Incident", back_populates="agent_runs")

    def __repr__(self) -> str:
        return f"<AgentRun {self.id} incident={self.incident_id} status={self.validation_status}>"
