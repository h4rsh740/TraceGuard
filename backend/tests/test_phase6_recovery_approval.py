"""Phase 6 tests: Recovery Agent, Admin Auth, Approval Gate, Idempotent Refunds,
and Webhook Incident Resolution.
"""

import uuid

from backend.app.agent.recovery import RecoveryAgent
from backend.app.core.config import settings
from backend.app.models.action import Action, ActionStatus, ActionType
from backend.app.models.evidence import Evidence, EvidenceKind
from backend.app.models.incident import Incident, IncidentStatus, IncidentType
from backend.app.services.event_store import EventStoreService
from backend.tests.test_phase3_webhook_eventstore import make_capture_payload, make_refund_payload

ADMIN_AUTH_HEADERS = {"X-Admin-Token": settings.ADMIN_PASSWORD}
BEARER_AUTH_HEADERS = {"Authorization": f"Bearer {settings.ADMIN_PASSWORD}"}
WRONG_AUTH_HEADERS = {"X-Admin-Token": "wrong_password_xyz"}


# ---------------------------------------------------------------------------
# Unit tests: Recovery Agent Drafting
# ---------------------------------------------------------------------------


def test_recovery_agent_drafts_refund_action(db_session):
    order_ref = f"ORD-REC-1-{uuid.uuid4().hex[:6]}"
    p1 = make_capture_payload(
        event_id=f"WH-REC1-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        resource_id="CAP-REC-1",
        amount="100.00",
    )
    p2 = make_capture_payload(
        event_id=f"WH-REC2-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        resource_id="CAP-REC-2",
        amount="100.00",
    )
    EventStoreService.store_event(db_session, p1)
    EventStoreService.store_event(db_session, p2)

    inc = Incident(
        order_ref=order_ref,
        type=IncidentType.DUPLICATE_PAYMENT.value,
        status=IncidentStatus.OPEN.value,
    )
    db_session.add(inc)
    db_session.commit()

    report = {
        "summary": "Duplicate payment detected on order.",
        "claims": [{"text": "Duplicate charge occurred.", "event_ids": [p2["id"]]}],
        "recommended_action": "REFUND",
        "target_resource_id": "CAP-REC-2",
        "confidence": 0.99,
        "unknowns": [],
    }

    action = RecoveryAgent.draft_action(db_session, inc.id, report)
    assert action is not None
    assert action.type == ActionType.REFUND.value
    assert action.status == ActionStatus.DRAFT.value  # Core Principle 3: ONLY drafts
    assert action.payload["capture_id"] == "CAP-REC-2"
    assert action.payload["amount"] == "100.00"
    assert action.idempotency_key.startswith("idemp_ref_")  # Core Principle 4: idempotency

    # Calling draft_action again returns the existing draft
    action_dup = RecoveryAgent.draft_action(db_session, inc.id, report)
    assert action_dup.id == action.id


def test_recovery_agent_drafts_dispute_action_from_vault(db_session):
    order_ref = f"ORD-REC-DISP-{uuid.uuid4().hex[:6]}"
    ev = Evidence.create_with_hash(
        order_ref=order_ref,
        kind=EvidenceKind.DELIVERY_PROOF.value,
        content="Signed carrier delivery receipt for ORD-REC-DISP",
    )
    db_session.add(ev)

    inc = Incident(order_ref=order_ref, type=IncidentType.DISPUTE_ITEM_NOT_RECEIVED.value)
    db_session.add(inc)
    db_session.commit()

    report = {
        "summary": "Dispute filed for delivered goods.",
        "claims": [],
        "recommended_action": "DISPUTE_EVIDENCE",
        "target_resource_id": "UNKNOWN",
        "confidence": 0.9,
        "unknowns": [],
    }

    action = RecoveryAgent.draft_action(db_session, inc.id, report)
    assert action is not None
    assert action.type == ActionType.DISPUTE_EVIDENCE.value
    assert action.status == ActionStatus.DRAFT.value
    assert action.payload["evidence_count"] == 1


# ---------------------------------------------------------------------------
# API tests: Admin Auth Protection on Approval Endpoints
# ---------------------------------------------------------------------------


def test_approval_endpoint_requires_admin_auth(client, db_session):
    inc = Incident(order_ref="ORD-AUTH-1", type=IncidentType.DUPLICATE_PAYMENT.value)
    db_session.add(inc)
    db_session.commit()

    act = Action(
        incident_id=inc.id,
        type=ActionType.REFUND.value,
        payload={"capture_id": "CAP-X"},
        status=ActionStatus.DRAFT.value,
        idempotency_key="idemp_auth_test_1",
    )
    db_session.add(act)
    db_session.commit()

    # 1. No auth headers -> 401
    res_no_auth = client.post(f"/actions/{act.id}/approve")
    assert res_no_auth.status_code == 401

    # 2. Wrong auth token -> 401
    res_wrong_auth = client.post(f"/actions/{act.id}/approve", headers=WRONG_AUTH_HEADERS)
    assert res_wrong_auth.status_code == 401

    # 3. Valid Bearer auth -> succeeds
    res_bearer = client.post(f"/actions/{act.id}/approve", headers=BEARER_AUTH_HEADERS)
    assert res_bearer.status_code == 200
    assert res_bearer.json()["status"] == "executed"


# ---------------------------------------------------------------------------
# Integration tests: Full Human Approval & Refund Execution
# ---------------------------------------------------------------------------


def test_approve_refund_action_executes_idempotent_refund(client, db_session):
    order_ref = f"ORD-APP-{uuid.uuid4().hex[:6]}"
    p1 = make_capture_payload(
        event_id=f"WH-APP1-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        resource_id="CAP-APP-1",
        amount="100.00",
    )
    p2 = make_capture_payload(
        event_id=f"WH-APP2-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        resource_id="CAP-APP-2",
        amount="100.00",
    )
    EventStoreService.store_event(db_session, p1)
    EventStoreService.store_event(db_session, p2)

    inc = Incident(
        order_ref=order_ref,
        type=IncidentType.DUPLICATE_PAYMENT.value,
        status=IncidentStatus.AWAITING_APPROVAL.value,
    )
    db_session.add(inc)
    db_session.commit()

    idemp_key = f"idemp_test_key_{uuid.uuid4().hex[:8]}"
    act = Action(
        incident_id=inc.id,
        type=ActionType.REFUND.value,
        payload={"capture_id": "CAP-APP-2", "amount": "100.00", "currency": "USD"},
        status=ActionStatus.DRAFT.value,
        idempotency_key=idemp_key,
    )
    db_session.add(act)
    db_session.commit()

    # Approve action via API
    res = client.post(
        f"/actions/{act.id}/approve",
        json={"approved_by": "alice_finance_manager"},
        headers=ADMIN_AUTH_HEADERS,
    )
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "executed"
    assert data["approved_by"] == "alice_finance_manager"
    assert data["idempotency_key"] == idemp_key
    assert "refund_result" in data

    # Verify action state in database
    db_session.refresh(act)
    assert act.status == ActionStatus.EXECUTED.value
    assert act.approved_by == "alice_finance_manager"
    assert act.approved_at is not None

    # Verify incident resolved
    db_session.refresh(inc)
    assert inc.status == IncidentStatus.RESOLVED.value

    # Cannot re-approve an already executed action
    res_repeat = client.post(
        f"/actions/{act.id}/approve",
        headers=ADMIN_AUTH_HEADERS,
    )
    assert res_repeat.status_code == 400


def test_reject_action(client, db_session):
    inc = Incident(
        order_ref="ORD-REJ-1",
        type=IncidentType.DUPLICATE_PAYMENT.value,
        status=IncidentStatus.AWAITING_APPROVAL.value,
    )
    db_session.add(inc)
    db_session.commit()

    act = Action(
        incident_id=inc.id,
        type=ActionType.REFUND.value,
        payload={"capture_id": "CAP-REJ"},
        status=ActionStatus.DRAFT.value,
        idempotency_key="idemp_rej_1",
    )
    db_session.add(act)
    db_session.commit()

    # Reject action via API
    res = client.post(
        f"/actions/{act.id}/reject",
        json={"rejected_by": "bob_compliance", "reason": "Customer agreed to keep extra item"},
        headers=ADMIN_AUTH_HEADERS,
    )
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "rejected"
    assert data["rejected_by"] == "bob_compliance"
    assert data["rejection_reason"] == "Customer agreed to keep extra item"

    # Verify incident marked rejected
    db_session.refresh(inc)
    assert inc.status == IncidentStatus.REJECTED.value


# ---------------------------------------------------------------------------
# Integration tests: Inbound Refund Webhook Resolves Incident (Section 5.6)
# ---------------------------------------------------------------------------


def test_refund_webhook_resolves_duplicate_incident(client, db_session):
    order_ref = f"ORD-WH-RES-{uuid.uuid4().hex[:6]}"

    # Event 1 & 2: Duplicate captures
    p1 = make_capture_payload(
        event_id=f"WH-WH1-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        amount="100.00",
    )
    p2 = make_capture_payload(
        event_id=f"WH-WH2-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        amount="100.00",
    )
    client.post("/webhooks/paypal", json=p1)
    res2 = client.post("/webhooks/paypal", json=p2)
    incident_id = res2.json()["incidents_triggered"][0]

    # Incident starts in open/awaiting_approval status
    inc = db_session.get(Incident, incident_id)
    assert inc.status in (IncidentStatus.OPEN.value, IncidentStatus.AWAITING_APPROVAL.value)

    # Event 3: Inbound PayPal refund webhook for the duplicate capture arrives!
    p_refund = make_refund_payload(
        event_id=f"WH-WH-REF-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        amount="100.00",
    )
    res3 = client.post("/webhooks/paypal", json=p_refund)
    assert res3.status_code == 200

    # Incident is now resolved by the incoming PayPal refund webhook!
    db_session.refresh(inc)
    assert inc.status == IncidentStatus.RESOLVED.value
