"""Payment provider adapters.

`mpesa` talks to Safaricom Daraja (STK Push to start a payment, STK Push Query
to confirm or reconcile it server-to-server). `simulator` exists only so the
full purchase flow can be exercised locally without credentials; it never
moves money, is refused by production settings, and payments it creates are
only completed by the `simulate_payment` management command.

Configure with PAYMENT_PROVIDER plus the MPESA_* environment variables
(see backend/.env.example and docs/PAYMENTS.md).
"""
import base64
import json
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.conf import settings


class MpesaError(Exception):
    """The provider could not be reached or refused the request. Message is safe to show users."""


# Daraja STK result codes that mean the payer actively stopped the payment.
CANCELLED_CODES = {1032}


def _request(url, *, method="GET", payload=None, headers=None, auth=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(url, data=data, headers=headers or {}, method=method)
    if auth:
        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    try:
        with urlopen(req, timeout=15) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        # Daraja reports "still processing" and validation errors as HTTP 500/400 with a JSON body.
        try:
            return json.loads(exc.read())
        except ValueError:
            raise MpesaError("The M-Pesa service could not be reached.") from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise MpesaError("The M-Pesa service could not be reached.") from exc


class MpesaDarajaProvider:
    name = "mpesa"

    def _host(self):
        return "https://sandbox.safaricom.co.ke" if settings.MPESA_ENV == "sandbox" else "https://api.safaricom.co.ke"

    def _require_config(self):
        required = (settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET, settings.MPESA_SHORTCODE,
                    settings.MPESA_PASSKEY, settings.MPESA_CALLBACK_URL, settings.MPESA_CALLBACK_TOKEN)
        if not all(required):
            raise MpesaError("M-Pesa is not configured. Add the Daraja credentials and callback URL.")

    def _token(self):
        token_data = _request(f"{self._host()}/oauth/v1/generate?grant_type=client_credentials",
                              auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET))
        access_token = token_data.get("access_token")
        if not access_token:
            raise MpesaError("M-Pesa did not issue an access token.")
        return access_token

    def _password(self):
        timestamp = datetime.now(ZoneInfo("Africa/Nairobi")).strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}".encode()).decode()
        return password, timestamp

    def initiate(self, *, amount, phone, reference, description="Nyumbani payment"):
        self._require_config()
        access_token = self._token()
        password, timestamp = self._password()
        callback_url = settings.MPESA_CALLBACK_URL.rstrip("/") + "/" + settings.MPESA_CALLBACK_TOKEN + "/"
        response = _request(
            f"{self._host()}/mpesa/stkpush/v1/processrequest", method="POST",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            payload={
                "BusinessShortCode": settings.MPESA_SHORTCODE, "Password": password,
                "Timestamp": timestamp, "TransactionType": settings.MPESA_TRANSACTION_TYPE,
                "Amount": int(amount), "PartyA": phone, "PartyB": settings.MPESA_PARTY_B or settings.MPESA_SHORTCODE,
                "PhoneNumber": phone, "CallBackURL": callback_url,
                "AccountReference": reference[:12], "TransactionDesc": description[:13],
            },
        )
        if response.get("ResponseCode") != "0" or not response.get("CheckoutRequestID"):
            raise MpesaError("M-Pesa did not accept the payment request.")
        return {
            "checkout_request_id": response["CheckoutRequestID"],
            "merchant_request_id": response.get("MerchantRequestID", ""),
            "customer_message": response.get("CustomerMessage", ""),
        }

    def query(self, checkout_request_id, payment=None):
        """Ask Daraja for the final state. Returns {"state": success|failed|cancelled|pending, ...}."""
        self._require_config()
        access_token = self._token()
        password, timestamp = self._password()
        response = _request(
            f"{self._host()}/mpesa/stkpushquery/v1/query", method="POST",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            payload={"BusinessShortCode": settings.MPESA_SHORTCODE, "Password": password,
                     "Timestamp": timestamp, "CheckoutRequestID": checkout_request_id},
        )
        if "ResultCode" not in response:
            # e.g. errorCode 500.001.1001 "The transaction is being processed".
            return {"state": "pending", "result_code": None, "result_desc": str(response.get("errorMessage", ""))[:255]}
        try:
            code = int(response["ResultCode"])
        except (TypeError, ValueError):
            return {"state": "pending", "result_code": None, "result_desc": "Unrecognised query response"}
        state = "success" if code == 0 else "cancelled" if code in CANCELLED_CODES else "failed"
        return {"state": state, "result_code": code, "result_desc": str(response.get("ResultDesc", ""))[:255]}


class SimulatorProvider:
    """Development-only stand-in. Never configured in production (see settings/prod.py)."""

    name = "simulator"

    def initiate(self, *, amount, phone, reference, description=""):
        if not settings.DEBUG:
            raise MpesaError("The payment simulator is disabled.")
        return {"checkout_request_id": f"SIM-{uuid4().hex}", "merchant_request_id": "",
                "customer_message": "Development simulator: run `python manage.py simulate_payment` to complete this payment."}

    def query(self, checkout_request_id, payment=None):
        if not settings.DEBUG:
            raise MpesaError("The payment simulator is disabled.")
        result = (payment.provider_payload or {}).get("simulated_result") if payment else None
        if result == "success":
            return {"state": "success", "result_code": 0, "result_desc": "Simulated success"}
        if result == "cancelled":
            return {"state": "cancelled", "result_code": 1032, "result_desc": "Simulated cancellation"}
        if result == "failed":
            return {"state": "failed", "result_code": 1, "result_desc": "Simulated failure"}
        return {"state": "pending", "result_code": None, "result_desc": "Simulated payment awaiting a result"}


def get_provider():
    if settings.PAYMENT_PROVIDER == "simulator":
        return SimulatorProvider()
    return MpesaDarajaProvider()
