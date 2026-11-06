"""Recovery Agent for drafting remediation actions from validated AI reports.

Strictly adheres to:
- Core Principle 3: The AI NEVER moves money. It only drafts an action for human approval.
- Core Principle 4: Refunds use PayPal-Request-Id idempotency key so actions can never execute twice.
"""

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.agent.tools import tool_get_evidence
from backend.app.models.action import Action, ActionStatus, ActionType
from backend.app.models.event import Event
from backend.app.models.incident import Incident

logger = logging.getLogger("traceguard.agent.recovery")


class RecoveryAgent:
    """Agent that synthesizes drafted remediation actions awaiting human authorization."""

    @staticmethod
    def get_existing_draft(db: Session, incident_id: str) -> Action | None:
        """Check if an action is already drafted or pending approval for this incident."""
        stmt = (
            select(Action)
            .where(
                Action.incident_id == incident_id,
                Action.status.in_([ActionStatus.DRAFT.value, ActionStatus.APPROVED.value]),
            )
            .order_by(Action.created_at.desc())
        )
        return db.scalars(stmt).first()

    @classmethod
    def draft_action(
        cls,
        db: Session,
        incident_id: str,
        report: dict[str, Any],
    ) -> Action | None:
        """Draft a remediation action (Refund or Dispute Evidence Packet) from a validated report.

        Does NOT execute the action. Action status is set strictly to 'draft'.
        """
        incident = db.get(Incident, incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found.")

        # Return existing draft if one is already pending
        existing = cls.get_existing_draft(db, incident.id)
        if existing:
            logger.info(
                "Returning existing draft action %s for incident %s", existing.id, incident.id
            )
            return existing

        recommended = str(report.get("recommended_action", "")).upper()
        target_resource = report.get("target_resource_id")

        if recommended == "REFUND":
            # 1. Resolve capture amount and currency from ground truth events
            events_stmt = (
                select(Event)
                .where(Event.order_ref == incident.order_ref)
                .order_by(Event.occurred_at.asc())
            )
            events = list(db.scalars(events_stmt).all())

            # Find matching capture event for target resource
            target_event = None
            for ev in events:
                if ev.resource_id == target_resource:
                    target_event = ev
                    break

            # Fallback to the latest capture event if target not directly matched
            if not target_event:
                for ev in reversed(events):
                    if "CAPTURE.COMPLETED" in ev.event_type:
                        target_event = ev
                        target_resource = ev.resource_id
                        break

            amount_val = (
                str(target_event.amount) if target_event and target_event.amount else "100.00"
            )
            currency_val = (
                target_event.currency if target_event and target_event.currency else "USD"
            )

            # 2. Generate unique idempotency key for PayPal-Request-Id
            idempotency_key = f"idemp_ref_{incident.id[:12]}_{uuid.uuid4().hex[:8]}"

            action = Action(
                incident_id=incident.id,
                type=ActionType.REFUND.value,
                payload={
                    "capture_id": target_resource,
                    "amount": amount_val,
                    "currency": currency_val,
                    "order_ref": incident.order_ref,
                    "reason": report.get("summary", "Duplicate charge remediation"),
                    "note_to_payer": f"TraceGuard refund for duplicate transaction on order {incident.order_ref}",
                },
                status=ActionStatus.DRAFT.value,
                idempotency_key=idempotency_key,
            )
            db.add(action)
            db.commit()
            db.refresh(action)
            logger.info(
                "Drafted REFUND action %s for incident %s (Target: %s, Amount: %s %s, Idempotency: %s)",
                action.id,
                incident.id,
                target_resource,
                amount_val,
                currency_val,
                idempotency_key,
            )
            return action

        elif recommended == "DISPUTE_EVIDENCE":
            # Assemble dispute packet from evidence vault
            evidence_records = tool_get_evidence(db, incident.order_ref)
            idempotency_key = f"idemp_disp_{incident.id[:12]}_{uuid.uuid4().hex[:8]}"

            action = Action(
                incident_id=incident.id,
                type=ActionType.DISPUTE_EVIDENCE.value,
                payload={
                    "order_ref": incident.order_ref,
                    "evidence_count": len(evidence_records),
                    "evidence_packet": evidence_records,
                    "summary": report.get("summary", "Dispute evidence submission packet"),
                },
                status=ActionStatus.DRAFT.value,
                idempotency_key=idempotency_key,
            )
            db.add(action)
            db.commit()
            db.refresh(action)
            logger.info(
                "Drafted DISPUTE_EVIDENCE action %s for incident %s with %d evidence items",
                action.id,
                incident.id,
                len(evidence_records),
            )
            return action

        logger.info("No actionable remediation drafted for recommendation '%s'", recommended)
        return None
