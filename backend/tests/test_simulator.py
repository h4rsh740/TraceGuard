"""Unit tests for the TraceGuard scenario simulator."""

import pytest

from backend.app.services.paypal_client import PayPalClient
from simulate import (
    run_dispute_scenario,
    run_duplicate_scenario,
    run_refund_mismatch_scenario,
    run_replay_scenario,
)


@pytest.mark.asyncio
async def test_simulator_duplicate_scenario_mock():
    client = PayPalClient(client_id="mock", client_secret="mock")
    result = await run_duplicate_scenario(
        client, order_ref="ORD-1001", amount="100.00", currency="USD", is_mock=True
    )

    assert result["scenario"] == "duplicate"
    assert result["order_ref"] == "ORD-1001"
    assert result["capture_1"].startswith("CAP-MOCK-1-")
    assert result["capture_2"].startswith("CAP-MOCK-2-")
    assert result["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_simulator_dispute_scenario():
    result = await run_dispute_scenario(order_ref="ORD-1002", is_mock=True)

    assert result["scenario"] == "dispute"
    assert result["order_ref"] == "ORD-1002"
    assert result["status"] == "SEEDED"
    assert result["dispute_id"].startswith("PP-D-SEEDED-")


@pytest.mark.asyncio
async def test_simulator_refund_mismatch_scenario():
    client = PayPalClient(client_id="mock", client_secret="mock")
    result = await run_refund_mismatch_scenario(
        client, order_ref="ORD-1003", amount="100.00", currency="USD", is_mock=True
    )

    assert result["scenario"] == "refund_mismatch"
    assert result["order_ref"] == "ORD-1003"
    assert result["original_amount"] == "100.00"
    assert result["refund_amount"] == "65.00"


def test_simulator_replay_scenario(capsys):
    run_replay_scenario("ORD-1001")
    captured = capsys.readouterr()
    assert "WITHOUT IDEMPOTENCY" in captured.out
    assert "WITH TRACEGUARD IDEMPOTENCY" in captured.out
    assert "PayPal-Request-Id" in captured.out
