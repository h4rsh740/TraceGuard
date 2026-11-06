"""PayPal Webhook receiver endpoint with signature verification and deduplication."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.services.event_store import EventStoreService
from backend.app.services.paypal_client import PayPalClient

logger = logging.getLogger("traceguard.webhook")

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
paypal_client = PayPalClient()


@router.post("/paypal", status_code=status.HTTP_200_OK)
async def receive_paypal_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Receive, verify, deduplicate, and record incoming PayPal Sandbox webhooks.

    1. Validates PayPal cryptographic signature.
    2. Deduplicates by paypal_event_id.
    3. Normalizes and appends event to the tamper-evident hash chain.
    4. Returns HTTP 200 immediately.
    """
    try:
        body = await request.json()
    except Exception as e:
        logger.error("Failed to parse JSON body: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON body",
        ) from e

    headers = dict(request.headers)

    # 1. Cryptographic Signature Verification
    is_valid = await paypal_client.verify_webhook_signature(headers, body)
    if not is_valid:
        logger.warning(
            "Rejected webhook: invalid signature from %s",
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook signature verification failed",
        )

    # 2. Deduplication and Event Store Recording
    event, is_duplicate = EventStoreService.store_event(db, body)

    if is_duplicate:
        return {
            "status": "duplicate",
            "message": "Event already recorded in Evidence Vault",
            "event_id": event.paypal_event_id,
            "order_ref": event.order_ref,
        }

    return {
        "status": "recorded",
        "event_id": event.paypal_event_id,
        "event_type": event.event_type,
        "order_ref": event.order_ref,
        "event_hash": event.event_hash,
    }
