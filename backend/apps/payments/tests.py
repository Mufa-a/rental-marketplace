import pytest
from django.test import override_settings

from . import services


def test_daraja_stk_push_builds_nairobi_password_and_callback(monkeypatch):
    calls = []

    def fake_request(url, **kwargs):
        calls.append((url, kwargs))
        if "/oauth/" in url:
            return {"access_token": "test-token"}
        return {"ResponseCode": "0", "CheckoutRequestID": "ws_CO_test", "CustomerMessage": "Check phone"}

    monkeypatch.setattr(services, "_request", fake_request)
    with override_settings(
        MPESA_CONSUMER_KEY="key", MPESA_CONSUMER_SECRET="secret",
        MPESA_SHORTCODE="123456", MPESA_PASSKEY="passkey", MPESA_ENV="sandbox",
        MPESA_CALLBACK_URL="https://market.example/api/v1/payments/mpesa/callback",
        MPESA_CALLBACK_TOKEN="random-token",
    ):
        result = services.initiate_stk_push(amount=500, phone="254712345678", reference="fee-12")

    assert result["CheckoutRequestID"] == "ws_CO_test"
    payload = calls[1][1]["payload"]
    assert payload["Amount"] == 500
    assert payload["PhoneNumber"] == "254712345678"
    assert payload["CallBackURL"].endswith("/random-token")
    assert payload["Timestamp"].startswith("202")
