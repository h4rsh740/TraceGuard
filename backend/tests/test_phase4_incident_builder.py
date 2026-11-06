"""Phase 4 tests: Incident Builder rules (R1, R2, R3), incident API endpoints,
and Scenario 1 end-to-end duplicate payment anomaly detection.
"""

import uuid

from backend.app.models.incident import Incident, IncidentStatus, IncidentType
from backend.app.services.event_store import EventStoreService
from backend.app.services.incident_builder import (
    evaluate_r1_duplicate_payment,
    evaluate_r2_refund_mismatch,
    evaluate_r3_dispute,
)
from backend.tests.test_phase3_webhook_eventstore import (
    make_capture_payload,
    make_dispute_payload,
    make_refund_payload,
)

# ---------------------------------------------------------------------------
# Unit tests: Rule R1 (Duplicate Payment)
# ---------------------------------------------------------------------------


def test_r1_single_capture_no_incident(db_session):
    order_ref = f"ORD-R1-SINGLE-{uuid.uuid4().hex[:6]}"
    p1 = make_capture_payload(
        event_id=f"WH-CAP-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        amount="100.00",
    )
    EventStoreService.store_event(db_session, p1)

    incident = evaluate_r1_duplicate_payment(db_session, order_ref)
    assert incident is None


def test_r1_two_captures_triggers_incident(db_session):
    order_ref = f"ORD-R1-DOUBLE-{uuid.uuid4().hex[:6]}"
    p1 = make_capture_payload(
        event_id=f"WH-CAP1-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        resource_id="CAP-1",
        amount="100.00",
        create_time="2026-10-31T10:00:00Z",
    )
    p2 = make_capture_payload(
        event_id=f"WH-CAP2-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        resource_id="CAP-2",
        amount="100.00",
        create_time="2026-10-31T10:01:00Z",
    )
    EventStoreService.store_event(db_session, p1)
    EventStoreService.store_event(db_session, p2)

    incident = evaluate_r1_duplicate_payment(db_session, order_ref)
    assert incident is not None
    assert incident.type == IncidentType.DUPLICATE_PAYMENT.value
    assert incident.status == IncidentStatus.OPEN.value
    assert incident.order_ref == order_ref
    assert incident.id.startswith("INC-")


def test_r1_idempotent_open_incident(db_session):
    order_ref = f"ORD-R1-IDEMP-{uuid.uuid4().hex[:6]}"
    p1 = make_capture_payload(event_id=f"WH-1-{uuid.uuid4().hex[:6]}", order_ref=order_ref)
    p2 = make_capture_payload(event_id=f"WH-2-{uuid.uuid4().hex[:6]}", order_ref=order_ref)
    p3 = make_capture_payload(event_id=f"WH-3-{uuid.uuid4().hex[:6]}", order_ref=order_ref)

    EventStoreService.store_event(db_session, p1)
    EventStoreService.store_event(db_session, p2)
    inc1 = evaluate_r1_duplicate_payment(db_session, order_ref)

    # 3rd capture shouldn't create a second incident
    EventStoreService.store_event(db_session, p3)
    inc2 = evaluate_r1_duplicate_payment(db_session, order_ref)

    assert inc1.id == inc2.id


# ---------------------------------------------------------------------------
# Unit tests: Rule R2 (Refund Mismatch)
# ---------------------------------------------------------------------------


def test_r2_matching_refund_no_incident(db_session):
    order_ref = f"ORD-R2-MATCH-{uuid.uuid4().hex[:6]}"
    p_cap = make_capture_payload(
        event_id=f"WH-CAP-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        amount="100.00",
    )
    p_ref = make_refund_payload(
        event_id=f"WH-REF-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        amount="100.00",
    )
    EventStoreService.store_event(db_session, p_cap)
    EventStoreService.store_event(db_session, p_ref)

    incident = evaluate_r2_refund_mismatch(db_session, order_ref)
    assert incident is None


def test_r2_mismatched_refund_triggers_incident(db_session):
    order_ref = f"ORD-R2-MISMATCH-{uuid.uuid4().hex[:6]}"
    p_cap = make_capture_payload(
        event_id=f"WH-CAP-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        amount="100.00",
    )
    p_ref = make_refund_payload(
        event_id=f"WH-REF-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        amount="65.00",
    )
    EventStoreService.store_event(db_session, p_cap)
    EventStoreService.store_event(db_session, p_ref)

    incident = evaluate_r2_refund_mismatch(db_session, order_ref)
    assert incident is not None
    assert incident.type == IncidentType.REFUND_MISMATCH.value
    assert incident.status == IncidentStatus.OPEN.value


# ---------------------------------------------------------------------------
# Unit tests: Rule R3 (Dispute)
# ---------------------------------------------------------------------------


def test_r3_dispute_triggers_incident(db_session):
    order_ref = f"ORD-R3-DISP-{uuid.uuid4().hex[:6]}"
    p_disp = make_dispute_payload(
        event_id=f"WH-DISP-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
    )
    EventStoreService.store_event(db_session, p_disp)

    incident = evaluate_r3_dispute(db_session, order_ref)
    assert incident is not None
    assert incident.type == IncidentType.DISPUTE_ITEM_NOT_RECEIVED.value
    assert incident.status == IncidentStatus.OPEN.value


# ---------------------------------------------------------------------------
# Integration tests: Webhook -> Incident Detection Pipeline
# ---------------------------------------------------------------------------


def test_webhook_triggers_r1_on_second_capture(client):
    order_ref = f"ORD-PIPE-{uuid.uuid4().hex[:6]}"

    # Event 1: First capture
    p1 = make_capture_payload(
        event_id=f"WH-PIPE-1-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        amount="100.00",
        create_time="2026-10-31T10:00:00Z",
    )
    r1 = client.post("/webhooks/paypal", json=p1)
    assert r1.status_code == 200
    assert r1.json()["incidents_triggered"] == []

    # Event 2: Second capture on same order_ref (timeout retry)
    p2 = make_capture_payload(
        event_id=f"WH-PIPE-2-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        amount="100.00",
        create_time="2026-10-31T10:02:00Z",
    )
    r2 = client.post("/webhooks/paypal", json=p2)
    assert r2.status_code == 200
    triggered = r2.json()["incidents_triggered"]
    assert len(triggered) == 1
    incident_id = triggered[0]
    assert incident_id.startswith("INC-")

    # Verify incident is in incident list API
    r_list = client.get("/incidents")
    assert r_list.status_code == 200
    items = r_list.json()["items"]
    found = [item for item in items if item["id"] == incident_id]
    assert len(found) == 1
    assert found[0]["type"] == "DUPLICATE_PAYMENT"
    assert found[0]["order_ref"] == order_ref
    assert found[0]["event_count"] == 2
    assert found[0]["amount"] == "100.00"


# ---------------------------------------------------------------------------
# Incident API Tests: GET /incidents & GET /incidents/{id}
# ---------------------------------------------------------------------------


def test_get_incident_detail_timeline_ordered_by_occurred_at(client):
    order_ref = f"ORD-TIME-{uuid.uuid4().hex[:6]}"

    # Post events out-of-order: event 2 has earlier create_time than event 1
    t1 = "2026-10-31T12:00:00Z"
    t2 = "2026-10-31T10:00:00Z"

    p1 = make_capture_payload(
        event_id=f"WH-T1-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        create_time=t1,
    )
    p2 = make_capture_payload(
        event_id=f"WH-T2-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        create_time=t2,
    )

    client.post("/webhooks/paypal", json=p1)
    res2 = client.post("/webhooks/paypal", json=p2)
    inc_id = res2.json()["incidents_triggered"][0]

    detail = client.get(f"/incidents/{inc_id}").json()
    assert detail["id"] == inc_id
    assert detail["order_ref"] == order_ref
    assert detail["type"] == "DUPLICATE_PAYMENT"

    # Timeline must be ordered by occurred_at (earliest first: t2 then t1)
    timeline = detail["timeline"]
    assert len(timeline) == 2
    assert timeline[0]["paypal_event_id"] == p2["id"]
    assert timeline[1]["paypal_event_id"] == p1["id"]
    assert timeline[0]["occurred_at"] < timeline[1]["occurred_at"]


def test_get_nonexistent_incident_returns_404(client):
    res = client.get("/incidents/INC-NONEXISTENT")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_list_incidents_filter_by_type_and_status(client, db_session):
    ref1 = f"ORD-F1-{uuid.uuid4().hex[:6]}"
    ref2 = f"ORD-F2-{uuid.uuid4().hex[:6]}"

    inc1 = Incident(
        order_ref=ref1, type=IncidentType.DUPLICATE_PAYMENT.value, status=IncidentStatus.OPEN.value
    )
    inc2 = Incident(
        order_ref=ref2,
        type=IncidentType.REFUND_MISMATCH.value,
        status=IncidentStatus.RESOLVED.value,
    )
    db_session.add(inc1)
    db_session.add(inc2)
    db_session.commit()

    # Filter by type
    r_type = client.get("/incidents?type=DUPLICATE_PAYMENT")
    assert r_type.status_code == 200
    types = [item["type"] for item in r_type.json()["items"]]
    assert all(t == "DUPLICATE_PAYMENT" for t in types)

    # Filter by status
    r_stat = client.get("/incidents?status=resolved")
    assert r_stat.status_code == 200
    statuses = [item["status"] for item in r_stat.json()["items"]]
    assert all(s == "resolved" for s in statuses)
