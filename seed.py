#!/usr/bin/env python3
"""Seed script for TraceGuard.

Populates the database with the 3 official demo scenarios:
1. ORD-1001: Duplicate Charge (2 captures of $100.00)
2. ORD-1002: 'Item Not Received' Dispute (1 capture of $150.00 + Evidence vault documents + Seeded dispute)
3. ORD-1003: Refund Mismatch (1 capture of $200.00 + 1 partial refund of $75.00)
"""

import logging
from datetime import UTC, datetime, timedelta

from backend.app.db.session import SessionLocal
from backend.app.models.evidence import Evidence, EvidenceKind
from backend.app.services.event_store import EventStoreService
from backend.app.services.incident_builder import run_all_rules

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed")


def seed_database() -> None:
    db = SessionLocal()
    try:
        logger.info("Starting TraceGuard database seeding...")
        now = datetime.now(UTC)

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
        run_all_rules(db, "ORD-1001")

        # -------------------------------------------------------------------
        # Scenario 2: 'Item Not Received' Dispute (ORD-1002) [SEEDED]
        # -------------------------------------------------------------------
        logger.info("Seeding Scenario 2: 'Item Not Received' Dispute (ORD-1002)...")
        # Evidence documents in Evidence Vault
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
        run_all_rules(db, "ORD-1002")

        # -------------------------------------------------------------------
        # Scenario 3: Refund Mismatch (ORD-1003)
        # -------------------------------------------------------------------
        logger.info("Seeding Scenario 3: Refund Mismatch (ORD-1003)...")
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

        logger.info("TraceGuard database seeding completed successfully!")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
