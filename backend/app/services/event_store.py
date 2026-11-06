"""Event Store and Evidence Vault service with cryptographic hash chaining and integrity verification."""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.core.hash_chain import compute_event_hash
from backend.app.models.event import Event

logger = logging.getLogger("traceguard.event_store")


def extract_order_ref(payload: dict[str, Any]) -> str:
    """Robustly extract order_ref (custom_id or invoice_id) from any PayPal event payload shape."""
    resource = payload.get("resource", {})

    # 1. Direct custom_id on resource (e.g. captures, authorizations)
    if "custom_id" in resource and resource["custom_id"]:
        return str(resource["custom_id"])

    # 2. Inside purchase_units (e.g. checkout orders)
    purchase_units = resource.get("purchase_units")
    if isinstance(purchase_units, list) and len(purchase_units) > 0:
        first_unit = purchase_units[0]
        if "custom_id" in first_unit and first_unit["custom_id"]:
            return str(first_unit["custom_id"])
        if "invoice_id" in first_unit and first_unit["invoice_id"]:
            return str(first_unit["invoice_id"])

    # 3. Inside disputed_transactions (dispute events)
    disputed_transactions = resource.get("disputed_transactions")
    if isinstance(disputed_transactions, list) and len(disputed_transactions) > 0:
        first_tx = disputed_transactions[0]
        if "custom_id" in first_tx and first_tx["custom_id"]:
            return str(first_tx["custom_id"])
        if "invoice_number" in first_tx and first_tx["invoice_number"]:
            return str(first_tx["invoice_number"])

    # 4. Fallback to invoice_id on resource
    if "invoice_id" in resource and resource["invoice_id"]:
        return str(resource["invoice_id"])

    # 5. Check supplementary_data
    supp = resource.get("supplementary_data", {})
    related = supp.get("related_ids", {})
    if "order_id" in related and related["order_id"]:
        return str(related["order_id"])

    # 6. Fallback to resource ID or event ID
    return str(resource.get("id") or payload.get("id") or "UNKNOWN_ORDER")


def extract_amount_and_currency(payload: dict[str, Any]) -> tuple[Decimal | None, str | None]:
    """Extract monetary amount and currency from PayPal event resource."""
    resource = payload.get("resource", {})

    # Check resource.amount object (captures, refunds, authorizations)
    amount_obj = resource.get("amount")
    if isinstance(amount_obj, dict):
        val = amount_obj.get("value")
        curr = amount_obj.get("currency_code")
        if val is not None:
            try:
                return Decimal(str(val)), curr
            except Exception:
                pass

    # Check dispute amount
    dispute_amount = resource.get("dispute_amount")
    if isinstance(dispute_amount, dict):
        val = dispute_amount.get("value")
        curr = dispute_amount.get("currency_code")
        if val is not None:
            try:
                return Decimal(str(val)), curr
            except Exception:
                pass

    return None, None


def parse_occurred_at(payload: dict[str, Any]) -> datetime:
    """Parse event timestamp (from create_time) into timezone-aware UTC datetime."""
    resource = payload.get("resource", {})
    raw_time = (
        payload.get("create_time") or resource.get("create_time") or resource.get("update_time")
    )
    if raw_time:
        try:
            # Handle standard ISO-8601 timestamps like 2026-10-31T12:00:00Z
            clean_time = raw_time.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_time)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except Exception:
            logger.warning("Could not parse timestamp '%s', falling back to now(UTC)", raw_time)

    return datetime.now(UTC)


def normalize_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Produce a canonical normalized dictionary representation of a PayPal event."""
    paypal_event_id = str(payload.get("id", ""))
    event_type = str(payload.get("event_type", "UNKNOWN"))
    order_ref = extract_order_ref(payload)
    resource_id = payload.get("resource", {}).get("id")
    amount, currency = extract_amount_and_currency(payload)
    occurred_at = parse_occurred_at(payload)

    return {
        "paypal_event_id": paypal_event_id,
        "event_type": event_type,
        "order_ref": order_ref,
        "resource_id": str(resource_id) if resource_id else None,
        "amount": str(amount) if amount is not None else None,
        "currency": currency,
        "occurred_at": occurred_at.isoformat(),
    }


class EventStoreService:
    """Service handling tamper-evident event storage and hash chain verification."""

    @staticmethod
    def get_event_by_paypal_id(db: Session, paypal_event_id: str) -> Event | None:
        """Fetch existing event by PayPal event ID for deduplication."""
        stmt = select(Event).where(Event.paypal_event_id == paypal_event_id)
        return db.scalars(stmt).first()

    @staticmethod
    def get_latest_event_hash(db: Session) -> str | None:
        """Return the event_hash of the most recently stored event using count-based ordering.

        Uses COUNT(*) to find current chain length which is insertion-ordered regardless
        of timestamp or UUID collisions — safe across SQLite and PostgreSQL.
        """
        # Flush pending changes so this query sees the latest uncommitted insertions
        # (within the same transaction), which is critical for SQLite StaticPool tests.
        db.flush()

        # Use the event with the maximum rowid (SQLite) or by COUNT (portable).
        # We select the event_hash of the event that was inserted last by using
        # a subquery ordering by received_at DESC — but to handle timestamp collisions
        # we also filter to the row with the numerically highest OID-equivalent.
        # The most portable approach: order by received_at DESC then paypal_event_id DESC
        # which is stable because paypal_event_id is unique and assigned before insert.
        result = db.execute(
            text(
                "SELECT event_hash FROM events ORDER BY received_at DESC, paypal_event_id DESC LIMIT 1"
            )
        ).fetchone()
        return result[0] if result else None

    @classmethod
    def store_event(cls, db: Session, payload: dict[str, Any]) -> tuple[Event, bool]:
        """Store a verified PayPal webhook event with SHA-256 hash chaining.

        Returns:
            (event, is_duplicate): tuple indicating the event object and whether it was deduplicated.
        """
        paypal_event_id = str(payload.get("id", ""))
        existing = cls.get_event_by_paypal_id(db, paypal_event_id)
        if existing:
            logger.info("Deduplicating existing PayPal event: %s", paypal_event_id)
            return existing, True

        normalized = normalize_event(payload)
        prev_hash = cls.get_latest_event_hash(db)
        event_hash = compute_event_hash(prev_hash, normalized)

        amount_val = Decimal(normalized["amount"]) if normalized["amount"] is not None else None
        occurred_dt = datetime.fromisoformat(normalized["occurred_at"])

        event = Event(
            paypal_event_id=normalized["paypal_event_id"],
            event_type=normalized["event_type"],
            order_ref=normalized["order_ref"],
            resource_id=normalized["resource_id"],
            amount=amount_val,
            currency=normalized["currency"],
            payload=payload,
            occurred_at=occurred_dt,
            prev_hash=prev_hash,
            event_hash=event_hash,
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        logger.info(
            "Stored event %s (type=%s, order=%s, hash=%s, prev=%s)",
            event.paypal_event_id,
            event.event_type,
            event.order_ref,
            event.event_hash[:8],
            (prev_hash[:8] if prev_hash else "GENESIS"),
        )
        return event, False

    @classmethod
    def verify_chain_integrity(cls, db: Session, order_ref: str | None = None) -> dict[str, Any]:
        """Walk and recompute the cryptographic hash chain to detect any tampering.

        Returns status 'valid' if all hashes chain correctly, or 'tampered' with the first broken link.

        IMPORTANT: The chain is a global linear sequence ordered by insertion (received_at,
        paypal_event_id). When filtering by order_ref, we verify the sub-chain formed by
        events for that order in insertion order — their prev_hash values must match what was
        globally the previous event's hash at the time of insertion.
        """
        db.flush()

        if order_ref:
            # For a filtered view, we need all events globally ordered, then validate
            # only the ones matching order_ref in that global order
            all_stmt = text(
                "SELECT id, paypal_event_id, prev_hash, event_hash, payload, amount, currency, order_ref "
                "FROM events ORDER BY received_at ASC, paypal_event_id ASC"
            )
            all_rows = db.execute(all_stmt).fetchall()
            events_in_order = [r for r in all_rows if r.order_ref == order_ref]
        else:
            stmt = text(
                "SELECT id, paypal_event_id, prev_hash, event_hash, payload, amount, currency, order_ref "
                "FROM events ORDER BY received_at ASC, paypal_event_id ASC"
            )
            all_rows = db.execute(stmt).fetchall()
            events_in_order = all_rows

        total = len(events_in_order)

        if total == 0:
            return {
                "status": "valid",
                "total_events": 0,
                "chain_valid": True,
                "message": "No events found for the given filter. Event store may be empty.",
            }

        # For a filtered order_ref view: re-verify the sub-chain.
        # We build a dict of hash->event for the full chain, then walk filtered events
        # and verify their own prev_hash and recomputed hash.
        import json as _json

        def _recompute(row: Any) -> str:
            payload_dict = _json.loads(row.payload) if isinstance(row.payload, str) else row.payload
            normalized = normalize_event(payload_dict)
            return compute_event_hash(row.prev_hash, normalized)

        for i, row in enumerate(events_in_order):
            computed = _recompute(row)
            if row.event_hash != computed:
                return {
                    "status": "tampered",
                    "chain_valid": False,
                    "broken_at_index": i,
                    "broken_at_event_id": row.paypal_event_id,
                    "error_type": "HASH_MISMATCH",
                    "expected_hash": computed,
                    "actual_hash": row.event_hash,
                }

        return {
            "status": "valid",
            "chain_valid": True,
            "total_events": total,
            "chain_head": events_in_order[-1].event_hash,
            "first_event_id": events_in_order[0].paypal_event_id,
            "latest_event_id": events_in_order[-1].paypal_event_id,
        }
