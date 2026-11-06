"""Integrity check endpoint for verifying the tamper-evident cryptographic hash chain."""

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.services.event_store import EventStoreService

router = APIRouter(prefix="/integrity", tags=["Integrity"])


@router.get("/verify", status_code=status.HTTP_200_OK)
def verify_hash_chain(
    order_ref: str | None = Query(
        None, description="Optional filter to verify chain for a specific order"
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Audit and recompute the SHA-256 hash chain across all stored events.

    Detects any database tampering, broken links, or modified historical records.
    """
    return EventStoreService.verify_chain_integrity(db, order_ref=order_ref)
