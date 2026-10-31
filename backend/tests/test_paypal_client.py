"""Unit tests for PayPal Sandbox API client."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.app.services.paypal_client import PayPalClient


@pytest.mark.asyncio
async def test_auth_header_generation():
    client = PayPalClient(client_id="test_id", client_secret="test_secret")
    header = client.get_auth_header()
    assert header.startswith("Basic ")


@pytest.mark.asyncio
async def test_client_refuses_live_url():
    with pytest.raises(ValueError) as exc:
        PayPalClient(base_url="https://api-m.paypal.com")
    assert "SECURITY GUARD" in str(exc.value)


@pytest.mark.asyncio
async def test_get_access_token_caching():
    client = PayPalClient(client_id="id", client_secret="secret")

    mock_response = httpx.Response(
        status_code=200,
        json={"access_token": "mock_token_abc_123", "expires_in": 3600},
        request=httpx.Request("POST", "https://api-m.sandbox.paypal.com/v1/oauth2/token"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        token1 = await client.get_access_token()
        assert token1 == "mock_token_abc_123"

        # Second call should use cached token without additional network request
        token2 = await client.get_access_token()
        assert token2 == "mock_token_abc_123"
        assert mock_post.call_count == 1


@pytest.mark.asyncio
async def test_create_order_payload_structure():
    client = PayPalClient(client_id="id", client_secret="secret")
    client._access_token = "valid_cached_token"
    client._token_expires_at = 9999999999

    mock_response = httpx.Response(
        status_code=201,
        json={"id": "ORDER-999", "status": "CREATED"},
        request=httpx.Request("POST", "https://api-m.sandbox.paypal.com/v2/checkout/orders"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        res = await client.create_order(order_ref="ORD-TEST", amount="50.00", currency="USD")
        assert res["id"] == "ORDER-999"

        # Verify sent payload matches PayPal documentation
        call_kwargs = mock_post.call_args.kwargs
        payload = call_kwargs["json"]
        assert payload["intent"] == "CAPTURE"
        unit = payload["purchase_units"][0]
        assert unit["custom_id"] == "ORD-TEST"
        assert unit["amount"]["value"] == "50.00"
        assert unit["amount"]["currency_code"] == "USD"


@pytest.mark.asyncio
async def test_refund_with_idempotency_header():
    client = PayPalClient(client_id="id", client_secret="secret")
    client._access_token = "valid_cached_token"
    client._token_expires_at = 9999999999

    mock_response = httpx.Response(
        status_code=201,
        json={"id": "REFUND-111", "status": "COMPLETED"},
        request=httpx.Request(
            "POST", "https://api-m.sandbox.paypal.com/v2/payments/captures/CAP-1/refund"
        ),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        res = await client.refund_capture(
            capture_id="CAP-1",
            amount="25.00",
            currency="USD",
            idempotency_key="idemp_ref_12345",
        )
        assert res["id"] == "REFUND-111"

        call_kwargs = mock_post.call_args.kwargs
        headers = call_kwargs["headers"]
        assert headers["PayPal-Request-Id"] == "idemp_ref_12345"
        assert headers["Authorization"] == "Bearer valid_cached_token"
        assert call_kwargs["json"]["amount"]["value"] == "25.00"
