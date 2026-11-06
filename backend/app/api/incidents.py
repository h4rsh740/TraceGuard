"""Incident management API endpoints for TraceGuard."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.event import Event
from backend.app.models.incident import Incident

router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.get("", status_code=status.HTTP_200_OK)
def list_incidents(
    status_filter: str | None = Query(None, alias="status"),
    type_filter: str | None = Query(None, alias="type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List detected incidents with status, anomaly type, and associated order details."""
    stmt = select(Incident).order_by(Incident.created_at.desc())

    if status_filter:
        stmt = stmt.where(Incident.status == status_filter)
    if type_filter:
        stmt = stmt.where(Incident.type == type_filter)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    incidents = list(db.scalars(stmt.offset(offset).limit(limit)).all())

    items = []
    for inc in incidents:
        # Fetch related events to compute summary metadata (total amount, event count)
        events_stmt = (
            select(Event).where(Event.order_ref == inc.order_ref).order_by(Event.occurred_at.asc())
        )
        related_events = list(db.scalars(events_stmt).all())

        latest_amount = None
        currency = None
        for ev in reversed(related_events):
            if ev.amount is not None:
                latest_amount = str(ev.amount)
                currency = ev.currency
                break

        items.append(
            {
                "id": inc.id,
                "order_ref": inc.order_ref,
                "type": inc.type,
                "status": inc.status,
                "created_at": inc.created_at.isoformat(),
                "updated_at": inc.updated_at.isoformat(),
                "event_count": len(related_events),
                "amount": latest_amount,
                "currency": currency,
            }
        )

    return {
        "total": total or 0,
        "items": items,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{incident_id}", status_code=status.HTTP_200_OK)
def get_incident(
    incident_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve full incident details including ordered event timeline and associated actions."""
    stmt = select(Incident).where(Incident.id == incident_id)
    incident = db.scalars(stmt).first()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )

    # Fetch event timeline ordered by occurred_at (per requirement 5.2)
    events_stmt = (
        select(Event)
        .where(Event.order_ref == incident.order_ref)
        .order_by(Event.occurred_at.asc(), Event.received_at.asc())
    )
    events = list(db.scalars(events_stmt).all())

    timeline = [
        {
            "id": ev.id,
            "paypal_event_id": ev.paypal_event_id,
            "event_type": ev.event_type,
            "resource_id": ev.resource_id,
            "amount": str(ev.amount) if ev.amount is not None else None,
            "currency": ev.currency,
            "occurred_at": ev.occurred_at.isoformat(),
            "received_at": ev.received_at.isoformat(),
            "event_hash": ev.event_hash,
            "prev_hash": ev.prev_hash,
            "payload": ev.payload,
        }
        for ev in events
    ]

    actions_data = [
        {
            "id": act.id,
            "type": act.type,
            "status": act.status,
            "payload": act.payload,
            "idempotency_key": act.idempotency_key,
            "approved_by": act.approved_by,
            "approved_at": act.approved_at.isoformat() if act.approved_at else None,
            "created_at": act.created_at.isoformat(),
        }
        for act in incident.actions
    ]

    agent_runs_data = [
        {
            "id": run.id,
            "model": run.model,
            "steps": run.steps,
            "tool_calls": run.tool_calls,
            "tokens_used": run.tokens_used,
            "claims": run.claims,
            "validation_status": run.validation_status,
            "validation_errors": run.validation_errors,
            "created_at": run.created_at.isoformat(),
        }
        for run in incident.agent_runs
    ]

    return {
        "id": incident.id,
        "order_ref": incident.order_ref,
        "type": incident.type,
        "status": incident.status,
        "created_at": incident.created_at.isoformat(),
        "updated_at": incident.updated_at.isoformat(),
        "timeline": timeline,
        "actions": actions_data,
        "agent_runs": agent_runs_data,
    }


@router.post("/{incident_id}/investigate", status_code=status.HTTP_200_OK)
async def run_investigation(
    incident_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Trigger the autonomous Investigator Agent on an incident.

    Uses tool calling, checks claims with the pure-code Report Validator,
    retries on errors, and stores an audit trail in agent_runs.
    """
    from backend.app.agent.investigator import InvestigatorAgent

    agent = InvestigatorAgent()
    try:
        report, agent_run = await agent.investigate(db, incident_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Investigation failed: {str(e)}",
        ) from e

    return {
        "incident_id": incident_id,
        "agent_run_id": agent_run.id,
        "validation_status": agent_run.validation_status,
        "validation_errors": agent_run.validation_errors,
        "tokens_used": agent_run.tokens_used,
        "report": report,
    }
