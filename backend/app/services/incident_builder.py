"""Incident builder: deterministic rule engine for detecting payment anomalies.

Three rules, evaluated in order on every new event for an order_ref:
  R1 DUPLICATE_PAYMENT    - 2+ successful captures linked to the same order_ref
  R2 REFUND_MISMATCH      - refund amount differs from capture without documented partial reason
  R3 DISPUTE_ITEM_NOT_RECEIVED - a customer dispute event exists for the order

Detection is 100% deterministic code. The LLM is never involved here.
Only completed events (from the Event store) drive rule evaluation.
"""

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.event import Event
from backend.app.models.incident import Incident, IncidentStatus, IncidentType

logger = logging.getLogger("traceguard.incident_builder")

# PayPal event types that signal a successful capture
CAPTURE_COMPLETED_TYPES = {
    "PAYMENT.CAPTURE.COMPLETED",
    "PAYMENT.ORDER.CAPTURED",
}

# PayPal event types that signal a refund
REFUND_EVENT_TYPES = {
    "PAYMENT.CAPTURE.REFUNDED",
    "PAYMENT.CAPTURE.REVERSED",
}

# PayPal event types that signal a dispute
DISPUTE_EVENT_TYPES = {
    "CUSTOMER.DISPUTE.CREATED",
    "RISK.DISPUTE.CREATED",
}


def _get_events_for_order(db: Session, order_ref: str) -> list[Event]:
    """Return all events for an order_ref ordered by occurred_at ascending."""
    db.flush()
    stmt = (
        select(Event)
        .where(Event.order_ref == order_ref)
        .order_by(Event.occurred_at.asc(), Event.paypal_event_id.asc())
    )
    return list(db.scalars(stmt).all())


def _get_existing_incident(db: Session, order_ref: str, incident_type: str) -> Incident | None:
    """Return an existing non-resolved incident for this order_ref+type, if any."""
    stmt = select(Incident).where(
        Incident.order_ref == order_ref,
        Incident.type == incident_type,
        Incident.status.notin_([IncidentStatus.RESOLVED, IncidentStatus.REJECTED]),
    )
    return db.scalars(stmt).first()


def _open_incident(db: Session, order_ref: str, incident_type: str) -> Incident:
    """Create and persist a new OPEN incident, idempotently (one open per type+order)."""
    existing = _get_existing_incident(db, order_ref, incident_type)
    if existing:
        logger.info(
            "Incident already open: %s for %s (type=%s)", existing.id, order_ref, incident_type
        )
        return existing

    incident = Incident(
        order_ref=order_ref,
        type=incident_type,
        status=IncidentStatus.OPEN,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    logger.info(
        "NEW INCIDENT OPENED: %s | order=%s | type=%s", incident.id, order_ref, incident_type
    )
    return incident


# ---------------------------------------------------------------------------
# Rule R1: DUPLICATE_PAYMENT
# ---------------------------------------------------------------------------


def evaluate_r1_duplicate_payment(db: Session, order_ref: str) -> Incident | None:
    """R1: Flag when 2+ successful captures exist for the same order_ref.

    This is a deterministic rule — no LLM involvement.
    Evidence: list of capture event IDs from the Event store.
    """
    events = _get_events_for_order(db, order_ref)
    captures = [e for e in events if e.event_type in CAPTURE_COMPLETED_TYPES]

    if len(captures) >= 2:
        capture_ids = [e.paypal_event_id for e in captures]
        logger.warning(
            "R1 DUPLICATE_PAYMENT detected for order %s: captures=%s", order_ref, capture_ids
        )
        return _open_incident(db, order_ref, IncidentType.DUPLICATE_PAYMENT)

    return None


# ---------------------------------------------------------------------------
# Rule R2: REFUND_MISMATCH
# ---------------------------------------------------------------------------


def evaluate_r2_refund_mismatch(db: Session, order_ref: str) -> Incident | None:
    """R2: Flag when a refund amount doesn't match the original capture amount.

    A partial refund is only valid if a documented partial-refund reason is present.
    At Phase 4 there is no partial-reason field yet, so any amount mismatch is flagged.
    Evidence: capture event and refund event from the Event store.
    """
    events = _get_events_for_order(db, order_ref)
    captures = [e for e in events if e.event_type in CAPTURE_COMPLETED_TYPES]
    refunds = [e for e in events if e.event_type in REFUND_EVENT_TYPES]

    if not captures or not refunds:
        return None

    # Compare the first capture amount against the first refund amount
    capture_amount: Decimal | None = captures[0].amount
    refund_amount: Decimal | None = refunds[0].amount

    if capture_amount is None or refund_amount is None:
        return None

    if capture_amount != refund_amount:
        logger.warning(
            "R2 REFUND_MISMATCH for order %s: capture=%s refund=%s",
            order_ref,
            capture_amount,
            refund_amount,
        )
        return _open_incident(db, order_ref, IncidentType.REFUND_MISMATCH)

    return None


# ---------------------------------------------------------------------------
# Rule R3: DISPUTE_ITEM_NOT_RECEIVED
# ---------------------------------------------------------------------------


def evaluate_r3_dispute(db: Session, order_ref: str) -> Incident | None:
    """R3: Flag when a dispute event exists for an order.

    Evidence: dispute event ID from the Event store.
    Note: PayPal Sandbox dispute API has limited coverage — seeded disputes use the
    same event interface and are labelled SEEDED in the UI and README.
    """
    events = _get_events_for_order(db, order_ref)
    disputes = [e for e in events if e.event_type in DISPUTE_EVENT_TYPES]

    if disputes:
        dispute_ids = [e.paypal_event_id for e in disputes]
        logger.warning(
            "R3 DISPUTE_ITEM_NOT_RECEIVED for order %s: disputes=%s", order_ref, dispute_ids
        )
        return _open_incident(db, order_ref, IncidentType.DISPUTE_ITEM_NOT_RECEIVED)

    return None


# ---------------------------------------------------------------------------
# Main entry point: run all rules after every new event
# ---------------------------------------------------------------------------


def check_incident_resolution(db: Session, order_ref: str) -> list[Incident]:
    """Check if an open or awaiting_approval incident has been resolved by subsequent events (e.g., refund).

    Per Section 5.6: The resulting PayPal refund webhook flows back into the event store and resolves the incident.
    """
    events = _get_events_for_order(db, order_ref)
    captures = [e for e in events if e.event_type in CAPTURE_COMPLETED_TYPES]
    refunds = [e for e in events if e.event_type in REFUND_EVENT_TYPES]

    resolved_list = []
    # If 2+ captures existed, but refund(s) now balance the extra capture(s):
    if len(captures) >= 2 and len(refunds) >= (len(captures) - 1):
        stmt = select(Incident).where(
            Incident.order_ref == order_ref,
            Incident.type == IncidentType.DUPLICATE_PAYMENT,
            Incident.status.in_(
                [
                    IncidentStatus.OPEN,
                    IncidentStatus.INVESTIGATING,
                    IncidentStatus.AWAITING_APPROVAL,
                ]
            ),
        )
        for inc in db.scalars(stmt).all():
            inc.status = IncidentStatus.RESOLVED.value
            resolved_list.append(inc)
            logger.info(
                "Incident %s resolved by inbound PayPal refund webhook for order %s",
                inc.id,
                order_ref,
            )

        if resolved_list:
            db.commit()

    return resolved_list


def run_all_rules(db: Session, order_ref: str) -> list[Incident]:
    """Evaluate all detection and resolution rules for an order_ref.

    Called by the webhook receiver after each new event is stored.
    Returns the list of incidents opened or modified.
    """
    # 1. Check if incoming event resolves any existing open incidents
    check_incident_resolution(db, order_ref)

    # 2. Check for anomalies requiring new incidents
    opened: list[Incident] = []

    inc = evaluate_r1_duplicate_payment(db, order_ref)
    if inc:
        opened.append(inc)

    inc = evaluate_r2_refund_mismatch(db, order_ref)
    if inc:
        opened.append(inc)

    inc = evaluate_r3_dispute(db, order_ref)
    if inc:
        opened.append(inc)

    return opened
