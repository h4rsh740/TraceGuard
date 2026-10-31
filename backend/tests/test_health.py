"""Tests for TraceGuard health endpoints and security guards."""

import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "TraceGuard"
    assert data["sandbox_mode"] is True


def test_health_check_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["sandbox_mode"] is True
    assert "sandbox.paypal.com" in data["paypal_base_url"]


def test_live_paypal_url_rejected():
    """Verify that TraceGuard strictly refuses to configure or start with a live PayPal URL."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(PAYPAL_BASE_URL="https://api-m.paypal.com")
    assert "CRITICAL SECURITY VIOLATION" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info2:
        Settings(PAYPAL_BASE_URL="https://api.paypal.com")
    assert "CRITICAL SECURITY VIOLATION" in str(exc_info2.value)
