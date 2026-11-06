"""Report Validator for TraceGuard.

Strictly enforces Core Principle 2:
- Plain deterministic code (NOT an LLM).
- Rejects any report where event IDs don't exist in the Event Store.
- Rejects claims where stated amounts don't match cited event data.
- Rejects target_resource_id if it does not belong to the incident's order.
"""

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.event import Event
from backend.app.models.incident import Incident


class ReportValidationError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__(f"Report validation failed with {len(errors)} error(s): {errors}")
        self.errors = errors


def extract_amounts_from_text(text: str) -> list[str]:
    """Find currency amounts mentioned in text (e.g. $100.00, $50, 100.00)."""
    # Matches patterns like $100.00, $50, 100.00 USD
    matches = re.findall(r"\$?\b([0-9]+\.[0-9]{2})\b", text)
    return matches


def validate_report(
    db: Session,
    incident_id: str,
    report: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Deterministically validate an AI investigation report against ground truth database records.

    Returns:
        (is_valid, list_of_errors): True and empty list if verified; False and error messages if rejected.
    """
    errors: list[str] = []

    # 1. Fetch incident record
    stmt = select(Incident).where(Incident.id == incident_id)
    incident = db.scalars(stmt).first()
    if not incident:
        return False, [f"Incident '{incident_id}' does not exist in database."]

    # 2. Structural schema checks
    required_keys = [
        "summary",
        "claims",
        "recommended_action",
        "target_resource_id",
        "confidence",
        "unknowns",
    ]
    for key in required_keys:
        if key not in report:
            errors.append(f"Missing required field '{key}' in report JSON.")

    if errors:
        return False, errors

    claims = report.get("claims", [])
    if not isinstance(claims, list):
        errors.append("Field 'claims' must be a list.")
        return False, errors

    # 3. Fetch ground truth events for this order
    events_stmt = select(Event).where(Event.order_ref == incident.order_ref)
    events = list(db.scalars(events_stmt).all())
    events_by_id = {ev.paypal_event_id: ev for ev in events}
    known_resource_ids = {ev.resource_id for ev in events if ev.resource_id}

    # 4. Validate each claim
    for idx, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"Claim #{idx + 1} must be an object with 'text' and 'event_ids'.")
            continue

        text = claim.get("text", "").strip()
        event_ids = claim.get("event_ids", [])

        if not text:
            errors.append(f"Claim #{idx + 1} has empty text.")

        if not isinstance(event_ids, list) or len(event_ids) == 0:
            errors.append(
                f"Claim #{idx + 1} ('{text[:40]}...') fails rule: must cite at least one event ID."
            )
            continue

        # Check every cited event ID exists for this order
        cited_events: list[Event] = []
        for eid in event_ids:
            if eid not in events_by_id:
                errors.append(
                    f"Claim cites non-existent or unlinked event ID '{eid}'. "
                    f"Order '{incident.order_ref}' only contains: {list(events_by_id.keys())}."
                )
            else:
                cited_events.append(events_by_id[eid])

        # Check amount consistency: if claim text states an amount, at least one cited event must match
        text_amounts = extract_amounts_from_text(text)
        if text_amounts and cited_events:
            cited_event_amounts = {
                f"{ev.amount:.2f}" for ev in cited_events if ev.amount is not None
            }
            for amt in text_amounts:
                if amt not in cited_event_amounts:
                    errors.append(
                        f"Amount mismatch in claim: stated ${amt}, but cited event(s) have amount(s): {list(cited_event_amounts)}."
                    )

    # 5. Validate target_resource_id
    recommended_action = str(report.get("recommended_action", "")).upper()
    target_resource = report.get("target_resource_id")

    if recommended_action != "NONE" and target_resource and target_resource != "UNKNOWN":
        if target_resource not in known_resource_ids:
            errors.append(
                f"Target resource ID '{target_resource}' does not belong to any event for order '{incident.order_ref}'. "
                f"Known resources: {list(known_resource_ids)}."
            )

    is_valid = len(errors) == 0
    return is_valid, errors
