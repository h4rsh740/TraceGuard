"""Event model for tamper-evident PayPal event storage."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Index, Numeric, String, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from backend.app.db.base import Base

JSONType = JSON().with_variant(postgresql.JSONB, "postgresql")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    paypal_event_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    order_ref: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)

    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (Index("ix_events_order_occurred", "order_ref", "occurred_at"),)

    def __repr__(self) -> str:
        return f"<Event {self.paypal_event_id} type={self.event_type} order={self.order_ref}>"
