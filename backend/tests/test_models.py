"""Tests for TraceGuard database models, hash chain, and tamper detection."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.app.core.hash_chain import compute_event_hash
from backend.app.models.action import Action, ActionStatus, ActionType
from backend.app.models.agent_run import AgentRun
from backend.app.models.event import Event
from backend.app.models.evidence import Evidence, EvidenceKind
from backend.app.models.incident import Incident, IncidentStatus, IncidentType


def test_event_model_and_hash_chain(db_session):
    now = datetime.now(UTC)
    raw_payload_1 = {"id": "WH-001", "event_type": "PAYMENT.CAPTURE.COMPLETED", "amount": "100.00"}
    norm_1 = {
        "paypal_event_id": "WH-001",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "order_ref": "ORD-1001",
        "resource_id": "CAP-001",
        "amount": "100.00",
        "currency": "USD",
        "occurred_at": now.isoformat(),
    }
    hash_1 = compute_event_hash(prev_hash=None, normalized_event=norm_1)

    event_1 = Event(
        paypal_event_id="WH-001",
        event_type="PAYMENT.CAPTURE.COMPLETED",
        order_ref="ORD-1001",
        resource_id="CAP-001",
        amount=Decimal("100.00"),
        currency="USD",
        payload=raw_payload_1,
        occurred_at=now,
        prev_hash=None,
        event_hash=hash_1,
    )
    db_session.add(event_1)
    db_session.commit()

    # Event 2 chained to Event 1
    raw_payload_2 = {"id": "WH-002", "event_type": "PAYMENT.CAPTURE.COMPLETED", "amount": "100.00"}
    norm_2 = {
        "paypal_event_id": "WH-002",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "order_ref": "ORD-1001",
        "resource_id": "CAP-002",
        "amount": "100.00",
        "currency": "USD",
        "occurred_at": now.isoformat(),
    }
    hash_2 = compute_event_hash(prev_hash=hash_1, normalized_event=norm_2)

    event_2 = Event(
        paypal_event_id="WH-002",
        event_type="PAYMENT.CAPTURE.COMPLETED",
        order_ref="ORD-1001",
        resource_id="CAP-002",
        amount=Decimal("100.00"),
        currency="USD",
        payload=raw_payload_2,
        occurred_at=now,
        prev_hash=hash_1,
        event_hash=hash_2,
    )
    db_session.add(event_2)
    db_session.commit()

    saved = db_session.query(Event).filter(Event.order_ref == "ORD-1001").all()
    assert len(saved) == 2
    assert saved[0].prev_hash is None
    assert saved[1].prev_hash == saved[0].event_hash


def test_hash_chain_tamper_detection():
    data = {"order_ref": "ORD-1001", "amount": "100.00"}
    original_hash = compute_event_hash(None, data)

    # Tampered data should yield different hash
    tampered_data = {"order_ref": "ORD-1001", "amount": "99.99"}
    tampered_hash = compute_event_hash(None, tampered_data)
    assert original_hash != tampered_hash


def test_incident_and_action_relationship(db_session):
    incident = Incident(
        order_ref="ORD-2002",
        type=IncidentType.DUPLICATE_PAYMENT.value,
        status=IncidentStatus.OPEN.value,
    )
    db_session.add(incident)
    db_session.commit()

    action = Action(
        incident_id=incident.id,
        type=ActionType.REFUND.value,
        payload={"capture_id": "CAP-2002-B", "amount": "50.00", "currency": "USD"},
        status=ActionStatus.DRAFT.value,
        idempotency_key="idemp_key_test_123",
    )
    db_session.add(action)
    db_session.commit()

    db_session.refresh(incident)
    assert len(incident.actions) == 1
    assert incident.actions[0].idempotency_key == "idemp_key_test_123"


def test_evidence_hashing(db_session):
    evidence_text = "Tracking #1Z9999999999999999 - Delivered to front porch at 10:45 AM"
    evidence = Evidence.create_with_hash(
        order_ref="ORD-3003",
        kind=EvidenceKind.DELIVERY_PROOF.value,
        content=evidence_text,
    )
    db_session.add(evidence)
    db_session.commit()

    retrieved = db_session.query(Evidence).filter_by(order_ref="ORD-3003").first()
    assert retrieved is not None
    assert len(retrieved.sha256) == 64


def test_agent_run_logging(db_session):
    incident = Incident(
        order_ref="ORD-4004",
        type=IncidentType.DUPLICATE_PAYMENT.value,
        status=IncidentStatus.INVESTIGATING.value,
    )
    db_session.add(incident)
    db_session.commit()

    run = AgentRun(
        incident_id=incident.id,
        model="gpt-4o-mini",
        steps=[{"step": 1, "thought": "Examining events for duplicate captures"}],
        tool_calls=[{"tool": "list_events", "args": {"order_ref": "ORD-4004"}}],
        tokens_used={"prompt_tokens": 120, "completion_tokens": 45, "total_tokens": 165},
        claims=[{"text": "Duplicate capture found", "event_ids": ["WH-001", "WH-002"]}],
        validation_status="verified",
        validation_errors=[],
    )
    db_session.add(run)
    db_session.commit()

    db_session.refresh(incident)
    assert len(incident.agent_runs) == 1
    assert incident.agent_runs[0].validation_status == "verified"
