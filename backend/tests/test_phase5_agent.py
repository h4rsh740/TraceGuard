"""Phase 5 tests: Investigator Agent, pure-code Report Validator, and agent_runs audit logging."""

import uuid

import pytest

from backend.app.agent.investigator import InvestigatorAgent
from backend.app.agent.tools import (
    tool_get_capture,
    tool_get_evidence,
    tool_get_incident,
    tool_list_events,
    tool_search_transactions,
)
from backend.app.agent.validator import validate_report
from backend.app.models.evidence import Evidence, EvidenceKind
from backend.app.models.incident import Incident, IncidentStatus, IncidentType
from backend.app.services.event_store import EventStoreService
from backend.tests.test_phase3_webhook_eventstore import make_capture_payload

# ---------------------------------------------------------------------------
# Unit tests: Investigator Agent Tools
# ---------------------------------------------------------------------------


def test_tool_get_incident(db_session):
    inc = Incident(
        order_ref="ORD-TOOL-1",
        type=IncidentType.DUPLICATE_PAYMENT.value,
        status=IncidentStatus.OPEN.value,
    )
    db_session.add(inc)
    db_session.commit()

    res = tool_get_incident(db_session, inc.id)
    assert res["id"] == inc.id
    assert res["order_ref"] == "ORD-TOOL-1"
    assert res["type"] == "DUPLICATE_PAYMENT"

    # Non-existent incident
    res_err = tool_get_incident(db_session, "INC-NONEXISTENT")
    assert "error" in res_err


def test_tool_list_events_and_search_transactions(db_session):
    order_ref = f"ORD-TOOL-2-{uuid.uuid4().hex[:6]}"
    p1 = make_capture_payload(
        event_id=f"WH-T1-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        resource_id="CAP-1",
        amount="100.00",
        create_time="2026-10-31T10:00:00Z",
    )
    p2 = make_capture_payload(
        event_id=f"WH-T2-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        resource_id="CAP-2",
        amount="100.00",
        create_time="2026-10-31T10:05:00Z",
    )
    EventStoreService.store_event(db_session, p1)
    EventStoreService.store_event(db_session, p2)

    events = tool_list_events(db_session, order_ref)
    assert len(events) == 2
    assert events[0]["paypal_event_id"] == p1["id"]

    tx_summary = tool_search_transactions(db_session, order_ref)
    assert tx_summary["order_ref"] == order_ref
    assert tx_summary["transaction_count"] == 2
    assert tx_summary["total_captured"] == 200.0
    assert tx_summary["net_amount"] == 200.0


def test_tool_get_evidence(db_session):
    order_ref = f"ORD-EVD-{uuid.uuid4().hex[:6]}"
    ev = Evidence.create_with_hash(
        order_ref=order_ref,
        kind=EvidenceKind.INVOICE.value,
        content="Invoice #987654 for Order ORD-EVD",
    )
    db_session.add(ev)
    db_session.commit()

    records = tool_get_evidence(db_session, order_ref)
    assert len(records) == 1
    assert records[0]["kind"] == "invoice"
    assert len(records[0]["sha256"]) == 64


@pytest.mark.asyncio
async def test_tool_get_capture_sandbox_fallback():
    res = await tool_get_capture("CAP-MOCK-TEST")
    assert res["id"] == "CAP-MOCK-TEST"
    assert res["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# Unit tests: Pure-Code Report Validator (Core Principle 2)
# ---------------------------------------------------------------------------


def test_validator_passes_valid_report(db_session):
    order_ref = f"ORD-VAL-OK-{uuid.uuid4().hex[:6]}"
    p1 = make_capture_payload(
        event_id=f"WH-VAL-1-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        resource_id="CAP-VAL-1",
        amount="100.00",
    )
    EventStoreService.store_event(db_session, p1)

    inc = Incident(order_ref=order_ref, type=IncidentType.DUPLICATE_PAYMENT.value)
    db_session.add(inc)
    db_session.commit()

    valid_report = {
        "summary": "Order ORD was charged $100.00 successfully.",
        "claims": [
            {
                "text": "Initial capture for $100.00 was recorded.",
                "event_ids": [p1["id"]],
            }
        ],
        "recommended_action": "REFUND",
        "target_resource_id": "CAP-VAL-1",
        "confidence": 0.95,
        "unknowns": [],
    }

    is_valid, errors = validate_report(db_session, inc.id, valid_report)
    assert is_valid is True
    assert errors == []


def test_validator_rejects_hallucinated_event_id(db_session):
    order_ref = f"ORD-VAL-FAIL-{uuid.uuid4().hex[:6]}"
    p1 = make_capture_payload(event_id=f"WH-VAL-REAL-{uuid.uuid4().hex[:6]}", order_ref=order_ref)
    EventStoreService.store_event(db_session, p1)

    inc = Incident(order_ref=order_ref, type=IncidentType.DUPLICATE_PAYMENT.value)
    db_session.add(inc)
    db_session.commit()

    fabricated_report = {
        "summary": "Fabricated claim test.",
        "claims": [
            {
                "text": "Claim citing non-existent event",
                "event_ids": ["WH-FABRICATED-999"],
            }
        ],
        "recommended_action": "NONE",
        "target_resource_id": "UNKNOWN",
        "confidence": 0.5,
        "unknowns": [],
    }

    is_valid, errors = validate_report(db_session, inc.id, fabricated_report)
    assert is_valid is False
    assert any("non-existent" in err for err in errors)


def test_validator_rejects_amount_mismatch(db_session):
    order_ref = f"ORD-VAL-AMT-{uuid.uuid4().hex[:6]}"
    p1 = make_capture_payload(
        event_id=f"WH-VAL-AMT-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        amount="100.00",
    )
    EventStoreService.store_event(db_session, p1)

    inc = Incident(order_ref=order_ref, type=IncidentType.DUPLICATE_PAYMENT.value)
    db_session.add(inc)
    db_session.commit()

    # Claim states $500.00, but real event is for $100.00
    mismatched_report = {
        "summary": "Amount mismatch test.",
        "claims": [
            {
                "text": "Payment capture for $500.00 occurred.",
                "event_ids": [p1["id"]],
            }
        ],
        "recommended_action": "NONE",
        "target_resource_id": "UNKNOWN",
        "confidence": 0.5,
        "unknowns": [],
    }

    is_valid, errors = validate_report(db_session, inc.id, mismatched_report)
    assert is_valid is False
    assert any("Amount mismatch" in err for err in errors)


def test_validator_rejects_target_resource_not_in_order(db_session):
    order_ref = f"ORD-VAL-RES-{uuid.uuid4().hex[:6]}"
    p1 = make_capture_payload(
        event_id=f"WH-VAL-RES-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        resource_id="CAP-REAL-123",
    )
    EventStoreService.store_event(db_session, p1)

    inc = Incident(order_ref=order_ref, type=IncidentType.DUPLICATE_PAYMENT.value)
    db_session.add(inc)
    db_session.commit()

    wrong_resource_report = {
        "summary": "Target resource mismatch test.",
        "claims": [{"text": "Valid claim text", "event_ids": [p1["id"]]}],
        "recommended_action": "REFUND",
        "target_resource_id": "CAP-ALIEN-999",  # Does NOT belong to this order!
        "confidence": 0.9,
        "unknowns": [],
    }

    is_valid, errors = validate_report(db_session, inc.id, wrong_resource_report)
    assert is_valid is False
    assert any("does not belong" in err for err in errors)


# ---------------------------------------------------------------------------
# Integration tests: Investigator Agent Execution & Audit Logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investigator_agent_full_run_with_audit_logging(db_session):
    order_ref = f"ORD-AGENT-{uuid.uuid4().hex[:6]}"

    # Set up scenario 1 duplicate payment events
    p1 = make_capture_payload(
        event_id=f"WH-AG1-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        resource_id="CAP-AG1",
        amount="100.00",
        create_time="2026-10-31T10:00:00Z",
    )
    p2 = make_capture_payload(
        event_id=f"WH-AG2-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        resource_id="CAP-AG2",
        amount="100.00",
        create_time="2026-10-31T10:02:00Z",
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

    agent = InvestigatorAgent()
    report, agent_run = await agent.investigate(db_session, inc.id)

    # 1. Report checks
    assert "summary" in report
    assert len(report["claims"]) >= 2
    assert report["recommended_action"] == "REFUND"
    assert report["target_resource_id"] == "CAP-AG2"

    # 2. Agent Run audit log checks
    assert agent_run.incident_id == inc.id
    assert agent_run.validation_status == "verified"
    assert agent_run.validation_errors == []
    assert len(agent_run.steps) >= 2
    assert len(agent_run.tool_calls) >= 1
    assert agent_run.tokens_used["total_tokens"] > 0

    # 3. Incident state transition
    db_session.refresh(inc)
    assert inc.status == IncidentStatus.AWAITING_APPROVAL.value


# ---------------------------------------------------------------------------
# API endpoint test: POST /incidents/{id}/investigate
# ---------------------------------------------------------------------------


def test_api_investigate_incident(client):
    order_ref = f"ORD-API-AG-{uuid.uuid4().hex[:6]}"
    p1 = make_capture_payload(
        event_id=f"WH-API1-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        resource_id="CAP-API-1",
        amount="100.00",
    )
    p2 = make_capture_payload(
        event_id=f"WH-API2-{uuid.uuid4().hex[:6]}",
        order_ref=order_ref,
        resource_id="CAP-API-2",
        amount="100.00",
    )
    client.post("/webhooks/paypal", json=p1)
    res2 = client.post("/webhooks/paypal", json=p2)
    incident_id = res2.json()["incidents_triggered"][0]

    # Trigger investigation via API
    inv_res = client.post(f"/incidents/{incident_id}/investigate")
    assert inv_res.status_code == 200
    data = inv_res.json()

    assert data["incident_id"] == incident_id
    assert data["validation_status"] == "verified"
    assert data["agent_run_id"].startswith("RUN-")
    assert "report" in data
    assert data["report"]["recommended_action"] == "REFUND"
    assert data["tokens_used"]["total_tokens"] > 0
