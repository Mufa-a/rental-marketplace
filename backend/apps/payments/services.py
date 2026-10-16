"""Safaricom Daraja STK Push integration with no SDK dependency."""
from django.db import transaction
from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from .models import ViewingCreditPurchase, ViewingCreditUse


BUNDLES = {1: 50, 3: 100, 5: 150, 10: 250}


def viewing_credit_balance(tenant):
    return tenant.credit_purchases.aggregate(total=Sum("credits_remaining"))["total"] or 0


@transaction.atomic
def reserve_viewing_credit(viewing_request):
    purchase = (ViewingCreditPurchase.objects.select_for_update()
                .filter(tenant=viewing_request.tenant, credits_remaining__gt=0,
                        payment__status="successful")
                .order_by("created_at", "id").first())
    if not purchase:
        raise ValidationError({"viewing_credits": "Buy a viewing bundle before requesting this home."})
    purchase.credits_remaining -= 1
    purchase.save(update_fields=("credits_remaining",))
    return ViewingCreditUse.objects.create(purchase=purchase, viewing_request=viewing_request)


@transaction.atomic
def settle_viewing_credit(viewing_request, *, restore=False):
    use = ViewingCreditUse.objects.select_for_update().filter(
        viewing_request=viewing_request, status=ViewingCreditUse.Status.RESERVED,
    ).first()
    if not use:
        return
    if restore:
        purchase = ViewingCreditPurchase.objects.select_for_update().get(pk=use.purchase_id)
        purchase.credits_remaining += 1
        purchase.save(update_fields=("credits_remaining",))
        use.status = ViewingCreditUse.Status.RESTORED
    else:
        use.status = ViewingCreditUse.Status.CONSUMED
    use.save(update_fields=("status",))
import base64
import json
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from django.conf import settings


class MpesaError(Exception):
    pass


def _request(url, *, method="GET", payload=None, headers=None, auth=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(url, data=data, headers=headers or {}, method=method)
    if auth:
        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    try:
        with urlopen(req, timeout=15) as response:
            return json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise MpesaError("The M-Pesa service could not be reached.") from exc


def initiate_stk_push(*, amount, phone, reference):
    required = (settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET,
                settings.MPESA_SHORTCODE, settings.MPESA_PASSKEY,
                settings.MPESA_CALLBACK_URL, settings.MPESA_CALLBACK_TOKEN)
    if not all(required):
        raise MpesaError("M-Pesa is not configured. Add the Daraja credentials and callback URL.")
    host = "https://sandbox.safaricom.co.ke" if settings.MPESA_ENV == "sandbox" else "https://api.safaricom.co.ke"
    token_data = _request(f"{host}/oauth/v1/generate?grant_type=client_credentials", auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET))
    access_token = token_data.get("access_token")
    if not access_token:
        raise MpesaError("M-Pesa did not issue an access token.")
    timestamp = datetime.now(ZoneInfo("Africa/Nairobi")).strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}".encode()).decode()
    callback_url = settings.MPESA_CALLBACK_URL.rstrip("/") + "/" + settings.MPESA_CALLBACK_TOKEN
    response = _request(
        f"{host}/mpesa/stkpush/v1/processrequest", method="POST",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        payload={
            "BusinessShortCode": settings.MPESA_SHORTCODE, "Password": password,
            "Timestamp": timestamp, "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount), "PartyA": phone, "PartyB": settings.MPESA_SHORTCODE,
            "PhoneNumber": phone, "CallBackURL": callback_url,
            "AccountReference": reference[:12], "TransactionDesc": "Rental fee",
        },
    )
    if response.get("ResponseCode") != "0" or not response.get("CheckoutRequestID"):
        raise MpesaError("M-Pesa did not accept the payment request.")
    return response
