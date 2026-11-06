#!/usr/bin/env python3
"""Seed script for TraceGuard.

Populates the database with rich demo scenarios and dummy data:
1. ORD-1001: Duplicate Charge ($100.00 x 2) - Investigated, Draft Action Ready for Approval.
2. ORD-1002: 'Item Not Received' Dispute ($150.00) [SEEDED] - Evidence Vault & Defense Packet.
3. ORD-1003: Refund Mismatch ($200.00 vs $75.00) - Open Anomaly (Click to Investigate live in UI).
4. ORD-1004: Resolved Duplicate ($450.00) - Full lifecycle completed & executed by lead_auditor.
5. ORD-1005: Clean Transaction ($49.99) - Normal verified event in SHA-256 hash chain.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from backend.app.agent.investigator import InvestigatorAgent
from backend.app.db.session import SessionLocal
from backend.app.models.action import Action, ActionStatus, ActionType
from backend.app.models.evidence import Evidence, EvidenceKind
from backend.app.models.incident import IncidentStatus
from backend.app.services.event_store import EventStoreService
from backend.app.services.incident_builder import run_all_rules
from backend.app.services.llm_client import LLMClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed")


async def seed_database_async() -> None:
    db = SessionLocal()
    try:
        logger.info("Starting TraceGuard database seeding with complete dummy dataset...")
        now = datetime.now(UTC)
        llm = LLMClient()
        investigator = InvestigatorAgent(llm_client=llm)

        # -------------------------------------------------------------------
        # Scenario 1: Duplicate Charge (ORD-1001)
        # -------------------------------------------------------------------
        logger.info("Seeding Scenario 1: Duplicate Charge (ORD-1001)...")
        cap1 = {
            "id": "WH-SEED-ORD1001-CAP1",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "create_time": (now - timedelta(minutes=45)).isoformat(),
            "resource": {
                "id": "CAP-ORD1001-1",
                "custom_id": "ORD-1001",
                "status": "COMPLETED",
                "amount": {"value": "100.00", "currency_code": "USD"},
                "create_time": (now - timedelta(minutes=45)).isoformat(),
            },
        }
        cap2 = {
            "id": "WH-SEED-ORD1001-CAP2",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "create_time": (now - timedelta(minutes=43)).isoformat(),
            "resource": {
                "id": "CAP-ORD1001-2",
                "custom_id": "ORD-1001",
                "status": "COMPLETED",
                "amount": {"value": "100.00", "currency_code": "USD"},
                "create_time": (now - timedelta(minutes=43)).isoformat(),
            },
        }
        EventStoreService.store_event(db, cap1)
        EventStoreService.store_event(db, cap2)
        incidents1 = run_all_rules(db, "ORD-1001")
        if incidents1:
            inc1 = incidents1[0]
            # Run autonomous investigation to prepare drafted action
            logger.info("Auto-investigating ORD-1001 to generate audit trail and draft action...")
            await investigator.investigate(db, inc1.id)

        # -------------------------------------------------------------------
        # Scenario 2: 'Item Not Received' Dispute (ORD-1002) [SEEDED]
        # -------------------------------------------------------------------
        logger.info("Seeding Scenario 2: 'Item Not Received' Dispute (ORD-1002)...")
        ev1 = Evidence.create_with_hash(
            order_ref="ORD-1002",
            kind=EvidenceKind.DELIVERY_PROOF.value,
            content="Carrier: UPS Ground | Tracking: 1Z9999999999999999 | Signed by: J. Doe | Delivery: 10:14 AM Front Porch",
        )
        ev2 = Evidence.create_with_hash(
            order_ref="ORD-1002",
            kind=EvidenceKind.INVOICE.value,
            content="Invoice #INV-2026-1002 | Customer: John Doe | Item: Ultra Mechanical Keyboard x1 | Total: $150.00 USD",
        )
        db.add(ev1)
        db.add(ev2)
        db.commit()

        disp_cap = {
            "id": "WH-SEED-ORD1002-CAP",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "create_time": (now - timedelta(days=2)).isoformat(),
            "resource": {
                "id": "CAP-ORD1002-1",
                "custom_id": "ORD-1002",
                "status": "COMPLETED",
                "amount": {"value": "150.00", "currency_code": "USD"},
                "create_time": (now - timedelta(days=2)).isoformat(),
            },
        }
        disp_evt = {
            "id": "WH-SEED-ORD1002-DISP",
            "event_type": "CUSTOMER.DISPUTE.CREATED",
            "create_time": (now - timedelta(hours=3)).isoformat(),
            "resource": {
                "id": "PP-D-SEEDED-ORD1002",
                "status": "OPEN",
                "dispute_amount": {"value": "150.00", "currency_code": "USD"},
                "dispute_reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
                "disputed_transactions": [
                    {
                        "custom_id": "ORD-1002",
                        "seller_transaction_id": "CAP-ORD1002-1",
                        "create_time": (now - timedelta(days=2)).isoformat(),
                    }
                ],
                "create_time": (now - timedelta(hours=3)).isoformat(),
            },
        }
        EventStoreService.store_event(db, disp_cap)
        EventStoreService.store_event(db, disp_evt)
        incidents2 = run_all_rules(db, "ORD-1002")
        if incidents2:
            inc2 = incidents2[0]
            logger.info("Auto-investigating ORD-1002 to compile dispute evidence packet...")
            await investigator.investigate(db, inc2.id)

        # -------------------------------------------------------------------
        # Scenario 3: Refund Mismatch (ORD-1003) - Left OPEN for interactive UI demo
        # -------------------------------------------------------------------
        logger.info("Seeding Scenario 3: Refund Mismatch (ORD-1003) - Ready for live UI demo...")
        mis_cap = {
            "id": "WH-SEED-ORD1003-CAP",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "create_time": (now - timedelta(hours=10)).isoformat(),
            "resource": {
                "id": "CAP-ORD1003-1",
                "custom_id": "ORD-1003",
                "status": "COMPLETED",
                "amount": {"value": "200.00", "currency_code": "USD"},
                "create_time": (now - timedelta(hours=10)).isoformat(),
            },
        }
        mis_ref = {
            "id": "WH-SEED-ORD1003-REF",
            "event_type": "PAYMENT.CAPTURE.REFUNDED",
            "create_time": (now - timedelta(hours=8)).isoformat(),
            "resource": {
                "id": "REF-ORD1003-1",
                "custom_id": "ORD-1003",
                "status": "COMPLETED",
                "amount": {"value": "75.00", "currency_code": "USD"},
                "create_time": (now - timedelta(hours=8)).isoformat(),
            },
        }
        EventStoreService.store_event(db, mis_cap)
        EventStoreService.store_event(db, mis_ref)
        run_all_rules(db, "ORD-1003")

        # -------------------------------------------------------------------
        # Scenario 4: Resolved High-Value Duplicate (ORD-1004) - Fully executed
        # -------------------------------------------------------------------
        logger.info("Seeding Scenario 4: Resolved High-Value Duplicate (ORD-1004)...")
        cap4_1 = {
            "id": "WH-SEED-ORD1004-CAP1",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "create_time": (now - timedelta(days=1, hours=2)).isoformat(),
            "resource": {
                "id": "CAP-ORD1004-1",
                "custom_id": "ORD-1004",
                "status": "COMPLETED",
                "amount": {"value": "450.00", "currency_code": "USD"},
                "create_time": (now - timedelta(days=1, hours=2)).isoformat(),
            },
        }
        cap4_2 = {
            "id": "WH-SEED-ORD1004-CAP2",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "create_time": (now - timedelta(days=1, hours=1)).isoformat(),
            "resource": {
                "id": "CAP-ORD1004-2",
                "custom_id": "ORD-1004",
                "status": "COMPLETED",
                "amount": {"value": "450.00", "currency_code": "USD"},
                "create_time": (now - timedelta(days=1, hours=1)).isoformat(),
            },
        }
        EventStoreService.store_event(db, cap4_1)
        EventStoreService.store_event(db, cap4_2)
        incidents4 = run_all_rules(db, "ORD-1004")
        if incidents4:
            inc4 = incidents4[0]
            # Create an already executed and approved Action
            act4 = Action(
                incident_id=inc4.id,
                type=ActionType.REFUND.value,
                status=ActionStatus.EXECUTED.value,
                idempotency_key="TG-SEED-EXEC-ORD1004-KEY",
                payload={"capture_id": "CAP-ORD1004-2", "amount": "450.00", "currency": "USD"},
                approved_by="lead_auditor",
                approved_at=now - timedelta(hours=20),
            )
            db.add(act4)
            inc4.status = IncidentStatus.RESOLVED.value
            db.commit()

        # -------------------------------------------------------------------
        # Scenario 5: Clean Standard Transaction (ORD-1005) - Verified clean
        # -------------------------------------------------------------------
        logger.info("Seeding Scenario 5: Clean Verified Transaction (ORD-1005)...")
        clean_app = {
            "id": "WH-SEED-ORD1005-APP",
            "event_type": "CHECKOUT.ORDER.APPROVED",
            "create_time": (now - timedelta(minutes=15)).isoformat(),
            "resource": {
                "id": "PP-ORD-1005",
                "custom_id": "ORD-1005",
                "create_time": (now - timedelta(minutes=15)).isoformat(),
            },
        }
        clean_cap = {
            "id": "WH-SEED-ORD1005-CAP",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "create_time": (now - timedelta(minutes=14)).isoformat(),
            "resource": {
                "id": "CAP-ORD1005-1",
                "custom_id": "ORD-1005",
                "status": "COMPLETED",
                "amount": {"value": "49.99", "currency_code": "USD"},
                "create_time": (now - timedelta(minutes=14)).isoformat(),
            },
        }
        EventStoreService.store_event(db, clean_app)
        EventStoreService.store_event(db, clean_cap)
        run_all_rules(db, "ORD-1005")

        logger.info("TraceGuard database seeding with dummy dataset completed successfully!")
    finally:
        db.close()


def main():
    asyncio.run(seed_database_async())


if __name__ == "__main__":
    main()
