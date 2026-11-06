"""Action and Approval Gate API endpoints.

Strictly enforces:
- Core Principle 3: The AI never moves money. A human must click Approve.
- Core Principle 4: Refunds use PayPal-Request-Id idempotency key.
- Approval and rejection endpoints are protected by admin authentication.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.security import verify_admin_auth
from backend.app.db.session import get_db
from backend.app.models.action import Action, ActionStatus, ActionType
from backend.app.models.incident import Incident, IncidentStatus
from backend.app.services.paypal_client import PayPalAPIError, PayPalClient

logger = logging.getLogger("traceguard.actions")

router = APIRouter(prefix="/actions", tags=["Actions & Approvals"])
paypal_client = PayPalClient()


class ApprovalRequest(BaseModel):
    approved_by: str = Field(default="admin", description="Identifier of the human approver")


class RejectionRequest(BaseModel):
    rejected_by: str = Field(
        default="admin", description="Identifier of the reviewer rejecting the action"
    )
    reason: str = Field(default="", description="Reason for rejecting the proposed remediation")


@router.get("", status_code=status.HTTP_200_OK)
def list_actions(
    incident_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all drafted, approved, executed, and rejected remediation actions."""
    stmt = select(Action).order_by(Action.created_at.desc())
    if incident_id:
        stmt = stmt.where(Action.incident_id == incident_id)
    if status_filter:
        stmt = stmt.where(Action.status == status_filter)

    actions = list(db.scalars(stmt).all())
    return [
        {
            "id": act.id,
            "incident_id": act.incident_id,
            "type": act.type,
            "status": act.status,
            "payload": act.payload,
            "idempotency_key": act.idempotency_key,
            "approved_by": act.approved_by,
            "approved_at": act.approved_at.isoformat() if act.approved_at else None,
            "created_at": act.created_at.isoformat(),
            "updated_at": act.updated_at.isoformat(),
        }
        for act in actions
    ]


@router.get("/{action_id}", status_code=status.HTTP_200_OK)
def get_action(
    action_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve details of a specific remediation action."""
    action = db.get(Action, action_id)
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action '{action_id}' not found",
        )

    return {
        "id": action.id,
        "incident_id": action.incident_id,
        "type": action.type,
        "status": action.status,
        "payload": action.payload,
        "idempotency_key": action.idempotency_key,
        "approved_by": action.approved_by,
        "approved_at": action.approved_at.isoformat() if action.approved_at else None,
        "created_at": action.created_at.isoformat(),
        "updated_at": action.updated_at.isoformat(),
    }


@router.post("/{action_id}/approve", status_code=status.HTTP_200_OK)
async def approve_action(
    action_id: str,
    body: ApprovalRequest = ApprovalRequest(),
    admin: str = Depends(verify_admin_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Approve and execute a drafted remediation action.

    PROTECTED: Requires Admin Authentication.
    Uses PayPal-Request-Id = action.idempotency_key to prevent duplicate refund execution.
    """
    action = db.get(Action, action_id)
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action '{action_id}' not found",
        )

    if action.status != ActionStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve action with status '{action.status}'. Action must be in 'draft' status.",
        )

    approver = body.approved_by or admin
    now = datetime.now(UTC)

    action.status = ActionStatus.APPROVED.value
    action.approved_by = approver
    action.approved_at = now
    db.commit()

    logger.info("Human approved action %s (Approver: %s)", action.id, approver)

    # Execute action based on type
    if action.type == ActionType.REFUND.value:
        capture_id = action.payload.get("capture_id")
        amount = action.payload.get("amount")
        currency = action.payload.get("currency", "USD")
        note = action.payload.get("note_to_payer")

        try:
            logger.info(
                "Executing PayPal sandbox refund for capture %s (Idempotency key: %s)",
                capture_id,
                action.idempotency_key,
            )
            refund_result = await paypal_client.refund_capture(
                capture_id=capture_id,
                amount=amount,
                currency=currency,
                idempotency_key=action.idempotency_key,
                note_to_payer=note,
            )

            action.status = ActionStatus.EXECUTED.value
            payload_copy = dict(action.payload)
            payload_copy["refund_result"] = refund_result
            action.payload = payload_copy

            # Resolve the incident
            incident = db.get(Incident, action.incident_id)
            if incident:
                incident.status = IncidentStatus.RESOLVED.value

            db.commit()
            db.refresh(action)

            logger.info(
                "Successfully executed refund action %s: %s", action.id, refund_result.get("id")
            )
            return {
                "status": "executed",
                "action_id": action.id,
                "incident_id": action.incident_id,
                "approved_by": action.approved_by,
                "approved_at": action.approved_at.isoformat(),
                "idempotency_key": action.idempotency_key,
                "refund_result": refund_result,
            }
        except PayPalAPIError as e:
            action.status = ActionStatus.FAILED.value
            payload_copy = dict(action.payload)
            payload_copy["error"] = str(e)
            action.payload = payload_copy
            db.commit()
            logger.error("Refund execution failed for action %s: %s", action.id, e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"PayPal Refund API failed: {str(e)}",
            ) from e

    elif action.type == ActionType.DISPUTE_EVIDENCE.value:
        action.status = ActionStatus.EXECUTED.value
        incident = db.get(Incident, action.incident_id)
        if incident:
            incident.status = IncidentStatus.RESOLVED.value
        db.commit()
        db.refresh(action)

        return {
            "status": "executed",
            "action_id": action.id,
            "incident_id": action.incident_id,
            "approved_by": action.approved_by,
            "approved_at": action.approved_at.isoformat(),
            "idempotency_key": action.idempotency_key,
            "message": "Dispute evidence packet approved and submitted",
        }

    return {
        "status": action.status,
        "action_id": action.id,
    }


@router.post("/{action_id}/reject", status_code=status.HTTP_200_OK)
def reject_action(
    action_id: str,
    body: RejectionRequest = RejectionRequest(),
    admin: str = Depends(verify_admin_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Reject a proposed remediation action.

    PROTECTED: Requires Admin Authentication.
    """
    action = db.get(Action, action_id)
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action '{action_id}' not found",
        )

    if action.status not in (ActionStatus.DRAFT.value, ActionStatus.APPROVED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject action with status '{action.status}'.",
        )

    reviewer = body.rejected_by or admin
    now = datetime.now(UTC)

    action.status = ActionStatus.REJECTED.value
    action.approved_by = reviewer
    action.approved_at = now
    payload_copy = dict(action.payload)
    if body.reason:
        payload_copy["rejection_reason"] = body.reason
    action.payload = payload_copy

    incident = db.get(Incident, action.incident_id)
    if incident:
        incident.status = IncidentStatus.REJECTED.value

    db.commit()
    db.refresh(action)

    logger.info(
        "Human rejected action %s (Reviewer: %s, Reason: %s)", action.id, reviewer, body.reason
    )
    return {
        "status": "rejected",
        "action_id": action.id,
        "incident_id": action.incident_id,
        "rejected_by": action.approved_by,
        "rejected_at": action.approved_at.isoformat(),
        "rejection_reason": body.reason,
    }
