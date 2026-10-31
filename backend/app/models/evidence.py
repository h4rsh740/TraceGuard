"""Evidence model for tamper-evident dispute packets and audit trails."""

import enum
import hashlib
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class EvidenceKind(enum.StrEnum):
    INVOICE = "invoice"
    DELIVERY_PROOF = "delivery_proof"
    CHAT = "chat"
    OTHER = "other"


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"EVD-{uuid.uuid4().hex[:12].upper()}"
    )
    order_ref: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_evidence_order_kind", "order_ref", "kind"),)

    @classmethod
    def create_with_hash(cls, order_ref: str, kind: str, content: str) -> "Evidence":
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return cls(order_ref=order_ref, kind=kind, content=content, sha256=checksum)

    def __repr__(self) -> str:
        return f"<Evidence {self.id} order={self.order_ref} kind={self.kind}>"
