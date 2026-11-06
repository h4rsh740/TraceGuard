"""
Phase 3 tests: Webhook receiver, event store hash chain, deduplication,
out-of-order handling, and integrity verification endpoint.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from backend.app.core.hash_chain import GENESIS_PREV_HASH, canonical_json, compute_event_hash
from backend.app.services.event_store import (
    EventStoreService,
    extract_amount_and_currency,
    extract_order_ref,
    normalize_event,
    parse_occurred_at,
)

# ---------------------------------------------------------------------------
# Fixtures: canonical PayPal webhook payloads
# ---------------------------------------------------------------------------


def make_capture_payload(
    event_id: str = "WH-TEST-001",
    order_ref: str = "ORD-9000",
    resource_id: str = "CAP-001",
    amount: str = "100.00",
    currency: str = "USD",
    create_time: str = "2026-10-31T10:00:00Z",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "create_time": create_time,
        "resource": {
            "id": resource_id,
            "custom_id": order_ref,
            "status": "COMPLETED",
            "amount": {"value": amount, "currency_code": currency},
            "create_time": create_time,
        },
    }


def make_refund_payload(
    event_id: str = "WH-TEST-002",
    order_ref: str = "ORD-9000",
    resource_id: str = "REF-001",
    amount: str = "50.00",
    currency: str = "USD",
    create_time: str = "2026-10-31T11:00:00Z",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "event_type": "PAYMENT.CAPTURE.REFUNDED",
        "create_time": create_time,
        "resource": {
            "id": resource_id,
            "custom_id": order_ref,
            "status": "COMPLETED",
            "amount": {"value": amount, "currency_code": currency},
            "create_time": create_time,
        },
    }


def make_dispute_payload(
    event_id: str = "WH-TEST-003",
    order_ref: str = "ORD-9001",
    dispute_id: str = "DISP-001",
    amount: str = "75.00",
    currency: str = "USD",
    create_time: str = "2026-10-31T12:00:00Z",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "event_type": "CUSTOMER.DISPUTE.CREATED",
        "create_time": create_time,
        "resource": {
            "id": dispute_id,
            "status": "OPEN",
            "dispute_amount": {"value": amount, "currency_code": currency},
            "disputed_transactions": [
                {
                    "id": "TXN-001",
                    "custom_id": order_ref,
                    "create_time": create_time,
                }
            ],
            "create_time": create_time,
        },
    }


# ---------------------------------------------------------------------------
# Unit tests: extract_order_ref
# ---------------------------------------------------------------------------


def test_extract_order_ref_from_resource_custom_id():
    payload = make_capture_payload(order_ref="ORD-1001")
    assert extract_order_ref(payload) == "ORD-1001"


def test_extract_order_ref_from_purchase_units():
    payload = {
        "id": "WH-ORDER-EVT",
        "event_type": "CHECKOUT.ORDER.APPROVED",
        "resource": {
            "id": "ORDER-XYZ",
            "purchase_units": [{"reference_id": "default", "custom_id": "ORD-5555"}],
        },
    }
    assert extract_order_ref(payload) == "ORD-5555"


def test_extract_order_ref_from_disputed_transactions():
    payload = make_dispute_payload(order_ref="ORD-9001")
    assert extract_order_ref(payload) == "ORD-9001"


def test_extract_order_ref_fallback_to_resource_id():
    payload = {"id": "WH-NO-REF", "event_type": "UNKNOWN.EVENT", "resource": {"id": "RES-999"}}
    assert extract_order_ref(payload) == "RES-999"


# ---------------------------------------------------------------------------
# Unit tests: extract_amount_and_currency
# ---------------------------------------------------------------------------


def test_extract_amount_from_capture():
    payload = make_capture_payload(amount="123.45", currency="USD")
    amount, currency = extract_amount_and_currency(payload)
    assert amount == Decimal("123.45")
    assert currency == "USD"


def test_extract_amount_from_dispute():
    payload = make_dispute_payload(amount="75.00", currency="EUR")
    amount, currency = extract_amount_and_currency(payload)
    assert amount == Decimal("75.00")
    assert currency == "EUR"


def test_extract_amount_missing_returns_none():
    payload = {"id": "WH-X", "event_type": "SOME.EVENT", "resource": {"id": "R-X"}}
    amount, currency = extract_amount_and_currency(payload)
    assert amount is None
    assert currency is None


# ---------------------------------------------------------------------------
# Unit tests: parse_occurred_at
# ---------------------------------------------------------------------------


def test_parse_occurred_at_z_suffix():
    payload = {"create_time": "2026-10-31T10:00:00Z", "resource": {}}
    dt = parse_occurred_at(payload)
    assert dt.tzinfo is not None
    assert dt.year == 2026
    assert dt.month == 10
    assert dt.day == 31
    assert dt.hour == 10


def test_parse_occurred_at_fallback_to_now():
    payload = {"resource": {}}  # no create_time
    before = datetime.now(UTC)
    dt = parse_occurred_at(payload)
    after = datetime.now(UTC)
    assert before <= dt <= after


# ---------------------------------------------------------------------------
# Unit tests: normalize_event
# ---------------------------------------------------------------------------


def test_normalize_event_produces_canonical_shape():
    payload = make_capture_payload(
        event_id="WH-NORM-001",
        order_ref="ORD-1001",
        resource_id="CAP-N001",
        amount="100.00",
        currency="USD",
    )
    normalized = normalize_event(payload)
    assert normalized["paypal_event_id"] == "WH-NORM-001"
    assert normalized["event_type"] == "PAYMENT.CAPTURE.COMPLETED"
    assert normalized["order_ref"] == "ORD-1001"
    assert normalized["resource_id"] == "CAP-N001"
    assert normalized["amount"] == "100.00"
    assert normalized["currency"] == "USD"
    assert "occurred_at" in normalized


# ---------------------------------------------------------------------------
# Unit tests: hash chain
# ---------------------------------------------------------------------------


def test_hash_chain_genesis_uses_zero_string():
    data = {"paypal_event_id": "WH-001", "event_type": "PAYMENT.CAPTURE.COMPLETED"}
    hash1 = compute_event_hash(None, data)
    hash_with_genesis = compute_event_hash(GENESIS_PREV_HASH, data)
    # Both None and explicit zero-string must produce the same hash
    assert hash1 == hash_with_genesis


def test_hash_chain_deterministic():
    data = {"paypal_event_id": "WH-002", "amount": "50.00"}
    h1 = compute_event_hash("abc123", data)
    h2 = compute_event_hash("abc123", data)
    assert h1 == h2


def test_hash_chain_sensitive_to_amount_change():
    data_original = {"paypal_event_id": "WH-003", "amount": "100.00", "order_ref": "ORD-1"}
    data_tampered = {"paypal_event_id": "WH-003", "amount": "1.00", "order_ref": "ORD-1"}
    h_orig = compute_event_hash("prev_hash_xyz", data_original)
    h_tampered = compute_event_hash("prev_hash_xyz", data_tampered)
    assert h_orig != h_tampered


def test_hash_chain_sensitive_to_prev_hash_change():
    data = {"paypal_event_id": "WH-004", "amount": "50.00"}
    h1 = compute_event_hash("prev_A", data)
    h2 = compute_event_hash("prev_B", data)
    assert h1 != h2


def test_canonical_json_key_order_irrelevant():
    # Same data, different insertion order -> same canonical JSON
    j1 = canonical_json({"b": 2, "a": 1})
    j2 = canonical_json({"a": 1, "b": 2})
    assert j1 == j2
    assert j1 == '{"a":1,"b":2}'


# ---------------------------------------------------------------------------
# Integration tests: EventStoreService with in-memory SQLite
# ---------------------------------------------------------------------------


def test_store_event_first_is_genesis(db_session):
    payload = make_capture_payload(event_id=f"WH-{uuid.uuid4().hex[:8]}", order_ref="ORD-G001")
    event, is_dup = EventStoreService.store_event(db_session, payload)
    assert is_dup is False
    assert event.prev_hash is None
    assert len(event.event_hash) == 64


def test_store_event_chains_to_previous(db_session):
    uid = uuid.uuid4().hex[:6]
    p1 = make_capture_payload(event_id=f"WH-{uid}-A", order_ref="ORD-CH01", resource_id="CAP-A")
    p2 = make_capture_payload(event_id=f"WH-{uid}-B", order_ref="ORD-CH01", resource_id="CAP-B")

    ev1, _ = EventStoreService.store_event(db_session, p1)
    ev2, _ = EventStoreService.store_event(db_session, p2)

    assert ev2.prev_hash == ev1.event_hash
    assert ev2.event_hash != ev1.event_hash


def test_store_event_deduplication(db_session):
    uid = uuid.uuid4().hex[:6]
    payload = make_capture_payload(event_id=f"WH-DUP-{uid}", order_ref="ORD-D001")
    ev1, is_dup1 = EventStoreService.store_event(db_session, payload)
    ev2, is_dup2 = EventStoreService.store_event(db_session, payload)

    assert is_dup1 is False
    assert is_dup2 is True
    assert ev1.paypal_event_id == ev2.paypal_event_id


def test_out_of_order_webhook_arrival(db_session):
    """Events arriving out of order must be stored in received_at order (hash chain is FIFO by receipt)."""
    uid = uuid.uuid4().hex[:6]
    # Event 2 happened first (earlier create_time) but arrives second
    p_late = make_capture_payload(
        event_id=f"WH-{uid}-LATE",
        order_ref="ORD-OOO",
        create_time="2026-10-31T10:00:00Z",  # occurred earlier
    )
    p_early = make_capture_payload(
        event_id=f"WH-{uid}-EARLY",
        order_ref="ORD-OOO",
        create_time="2026-10-31T12:00:00Z",  # occurred later
    )

    # Store "late" (out-of-order) first, then "early"
    ev1, _ = EventStoreService.store_event(db_session, p_late)
    ev2, _ = EventStoreService.store_event(db_session, p_early)

    # occurred_at reflects the PayPal create_time, not insertion order
    assert ev1.occurred_at < ev2.occurred_at
    # But the chain links in insertion order
    assert ev2.prev_hash == ev1.event_hash


# ---------------------------------------------------------------------------
# Integration tests: verify_chain_integrity
# ---------------------------------------------------------------------------


def test_integrity_empty_store(db_session):
    result = EventStoreService.verify_chain_integrity(db_session)
    assert result["status"] == "valid"
    assert result["chain_valid"] is True
    assert result["total_events"] == 0


def test_integrity_valid_chain(db_session):
    uid = uuid.uuid4().hex[:6]
    payloads = [
        make_capture_payload(event_id=f"WH-INT-{uid}-{i}", order_ref="ORD-INTEG") for i in range(3)
    ]
    for p in payloads:
        EventStoreService.store_event(db_session, p)

    result = EventStoreService.verify_chain_integrity(db_session, order_ref="ORD-INTEG")
    assert result["status"] == "valid"
    assert result["chain_valid"] is True
    assert result["total_events"] == 3


def test_integrity_detects_tampered_hash(db_session):
    uid = uuid.uuid4().hex[:6]
    p1 = make_capture_payload(event_id=f"WH-TAMP-{uid}-A", order_ref="ORD-TAMP")
    p2 = make_capture_payload(event_id=f"WH-TAMP-{uid}-B", order_ref="ORD-TAMP")

    ev1, _ = EventStoreService.store_event(db_session, p1)
    ev2, _ = EventStoreService.store_event(db_session, p2)

    # Directly mutate ev1's hash to simulate DB tampering
    ev1.event_hash = "a" * 64
    db_session.commit()

    result = EventStoreService.verify_chain_integrity(db_session, order_ref="ORD-TAMP")
    assert result["status"] == "tampered"
    assert result["chain_valid"] is False
    # ev1 is at index 0, ev2 is at index 1; ev2's prev_hash no longer matches
    assert result["broken_at_event_id"] in (
        f"WH-TAMP-{uid}-A",
        f"WH-TAMP-{uid}-B",
    )


# ---------------------------------------------------------------------------
# API endpoint tests: POST /webhooks/paypal
# ---------------------------------------------------------------------------


def test_webhook_endpoint_records_event(client):
    payload = make_capture_payload(
        event_id=f"WH-API-{uuid.uuid4().hex[:8]}",
        order_ref="ORD-API01",
    )
    # Mock WEBHOOK_ID is "mock_webhook_id" -> test bypass triggers in paypal_client
    response = client.post("/webhooks/paypal", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recorded"
    assert data["event_type"] == "PAYMENT.CAPTURE.COMPLETED"
    assert data["order_ref"] == "ORD-API01"
    assert len(data["event_hash"]) == 64


def test_webhook_endpoint_deduplicates(client):
    payload = make_capture_payload(
        event_id=f"WH-DUP-API-{uuid.uuid4().hex[:8]}",
        order_ref="ORD-API02",
    )
    r1 = client.post("/webhooks/paypal", json=payload)
    r2 = client.post("/webhooks/paypal", json=payload)
    assert r1.status_code == 200
    assert r1.json()["status"] == "recorded"
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate"


def test_webhook_endpoint_rejects_invalid_signature(client):
    payload = make_capture_payload(event_id=f"WH-BAD-{uuid.uuid4().hex[:8]}")
    # Send the x-traceguard-test-auth: invalid header to force signature failure
    response = client.post(
        "/webhooks/paypal",
        json=payload,
        headers={"x-traceguard-test-auth": "invalid"},
    )
    assert response.status_code == 400
    assert "signature" in response.json()["detail"].lower()


def test_webhook_endpoint_rejects_malformed_json(client):
    response = client.post(
        "/webhooks/paypal",
        content=b"not valid json }{",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# API endpoint tests: GET /integrity/verify
# ---------------------------------------------------------------------------


def test_integrity_endpoint_empty(client):
    response = client.get("/integrity/verify")
    assert response.status_code == 200
    data = response.json()
    assert data["chain_valid"] is True


def test_integrity_endpoint_after_events(client):
    uid = uuid.uuid4().hex[:6]
    for i in range(3):
        payload = make_capture_payload(
            event_id=f"WH-INTGR-{uid}-{i}",
            order_ref=f"ORD-INTGR-{uid}",
        )
        client.post("/webhooks/paypal", json=payload)

    response = client.get(f"/integrity/verify?order_ref=ORD-INTGR-{uid}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "valid"
    assert data["total_events"] == 3
