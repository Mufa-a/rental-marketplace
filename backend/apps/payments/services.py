"""Payment lifecycle, configurable prices and viewing-credit accounting.

Rules this module enforces:
* Value (credits, a paid fee, a verification review) is granted only after the
  provider confirms payment server-side: a callback that is cross-checked with
  an STK Push Query, or a query made during reconciliation. A frontend can
  never mark a payment successful.
* Every state change is idempotent: a payment is fulfilled at most once, a
  provider receipt can settle only one payment, and retried requests with the
  same idempotency key return the original payment.
* A payment that never receives a callback does not block the user: after
  PAYMENT_QUERY_AFTER_SECONDS it is reconciled with the provider, and after
  PAYMENT_TIMEOUT_MINUTES without a final answer it is marked failed. A late
  success for a timed-out payment is still honoured, because money moved.
"""
import re
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.models import AuditLog
from apps.notifications.services import notify

from .models import Payment, ReferralFeeRule, ServicePrice, ViewingCreditPurchase, ViewingCreditUse, ViewingPackage
from .providers import MpesaError, get_provider  # noqa: F401  (MpesaError is re-exported for callers)

TIMEOUT_REASON = "timeout"


def _audit(actor, action, obj, **metadata):
    AuditLog.objects.create(actor=actor, action=action, object_type=obj._meta.label, object_id=str(obj.pk), metadata=metadata)


def _bust_public_cache():
    from apps.properties.views import _invalidate_public_listing_cache
    _invalidate_public_listing_cache()


# ---------------------------------------------------------------- prices

def default_country():
    return settings.DEFAULT_COUNTRY


def active_packages(country=None):
    return ViewingPackage.objects.filter(country=country or default_country(), is_active=True).order_by("sort_order", "credits")


def service_price(code, country=None):
    price = ServicePrice.objects.filter(country=country or default_country(), code=code, is_active=True).first()
    if price is None:
        raise ValidationError({"price": "This service is not available in your country yet."})
    return price


def referral_fee_for(rent, country=None):
    rule = (ReferralFeeRule.objects
            .filter(country=country or default_country(), is_active=True, min_rent__lte=rent)
            .filter(Q(max_rent__isnull=True) | Q(max_rent__gte=rent))
            .order_by("-min_rent").first())
    if rule is None:
        raise ValidationError({"referral_fee": "No referral fee rule covers this rent. An administrator must configure one."})
    return rule.fee_for(rent)


# ---------------------------------------------------------------- credits

def viewing_credit_balance(tenant, country=None):
    purchases = tenant.credit_purchases.filter(payment__status=Payment.Status.SUCCESSFUL)
    if country:
        purchases = purchases.filter(country=country)
    return purchases.aggregate(total=Sum("credits_remaining"))["total"] or 0


@transaction.atomic
def reserve_viewing_credit(viewing_request):
    """Set one credit aside for a new request. Oldest purchase first; matching country only."""
    purchase = (ViewingCreditPurchase.objects.select_for_update()
                .filter(tenant=viewing_request.tenant, credits_remaining__gt=0,
                        country=viewing_request.unit.property.country,
                        payment__status=Payment.Status.SUCCESSFUL)
                .order_by("created_at", "id").first())
    if not purchase:
        raise ValidationError({"viewing_credits": "Buy a viewing package before requesting this home."})
    purchase.credits_remaining -= 1
    purchase.save(update_fields=("credits_remaining",))
    return ViewingCreditUse.objects.create(purchase=purchase, viewing_request=viewing_request)


@transaction.atomic
def settle_viewing_credit(viewing_request, *, restore=False, include_consumed=False):
    """Consume (landlord approved) or restore (declined / cancelled / expired) a request's credit.

    include_consumed=True also returns a credit that was already consumed — used when the
    landlord cancels an approved viewing, which is not the tenant's fault.
    """
    statuses = [ViewingCreditUse.Status.RESERVED]
    if include_consumed:
        statuses.append(ViewingCreditUse.Status.CONSUMED)
    use = ViewingCreditUse.objects.select_for_update().filter(viewing_request=viewing_request, status__in=statuses).first()
    if not use:
        return None
    if restore:
        purchase = ViewingCreditPurchase.objects.select_for_update().get(pk=use.purchase_id)
        if purchase.payment.status == Payment.Status.SUCCESSFUL:
            purchase.credits_remaining += 1
            purchase.save(update_fields=("credits_remaining",))
        use.status = ViewingCreditUse.Status.RESTORED
    else:
        use.status = ViewingCreditUse.Status.CONSUMED
    use.save(update_fields=("status", "updated_at"))
    return use


# ---------------------------------------------------------------- starting payments

def _digits(phone):
    return re.sub(r"\D", "", phone)


def reconcile_if_stale(payment):
    """Bring a pending payment up to date with the provider if it has waited too long."""
    if payment.status != Payment.Status.PENDING:
        return payment
    age = timezone.now() - payment.created_at
    if age < timedelta(seconds=settings.PAYMENT_QUERY_AFTER_SECONDS):
        return payment
    return reconcile_payment(payment.pk)


def blocking_pending(queryset):
    """The first pending payment in queryset that is still genuinely in flight, after reconciliation."""
    for payment in queryset.filter(status=Payment.Status.PENDING).order_by("created_at"):
        if reconcile_if_stale(payment).status == Payment.Status.PENDING:
            return payment
    return None


def start_payment(*, actor, purpose, amount, phone, idempotency_key, reference, description, **links):
    """Create (or return the existing) payment for an idempotency key and send the STK prompt.

    Returns (payment, created). Raises MpesaError when the provider refuses; the payment is
    then recorded as failed so the user can retry immediately.
    """
    defaults = {"purpose": purpose, "amount": amount, "phone_number": phone, "provider": settings.PAYMENT_PROVIDER,
                "provider_reference": f"pending:{uuid4().hex}", **links}
    try:
        with transaction.atomic():
            payment, created = Payment.objects.get_or_create(idempotency_key=idempotency_key, defaults=defaults)
    except IntegrityError:
        payment, created = Payment.objects.get(idempotency_key=idempotency_key), False
    if payment.purpose != purpose or payment.amount != amount or any(getattr(payment, field) != value for field, value in links.items()):
        raise ValidationError({"idempotency_key": "That payment key was already used for a different purchase."})
    if not created:
        return payment, False
    try:
        result = get_provider().initiate(amount=amount, phone=_digits(phone), reference=reference.format(id=payment.pk), description=description)
    except MpesaError as exc:
        payment.status = Payment.Status.FAILED
        payment.failure_reason = "provider_error"
        payment.provider_payload = {"error": str(exc)}
        payment.save(update_fields=("status", "failure_reason", "provider_payload", "updated_at"))
        _audit(actor, "payment.initiation_failed", payment, purpose=purpose)
        raise
    payment.provider_reference = result["checkout_request_id"]
    payment.provider_payload = {"merchant_request_id": result.get("merchant_request_id", ""),
                                "customer_message": result.get("customer_message", "")}
    payment.save(update_fields=("provider_reference", "provider_payload", "updated_at"))
    _audit(actor, "payment.initiated", payment, purpose=purpose, amount=amount)
    return payment, True


# ---------------------------------------------------------------- results

def _can_accept_result(payment):
    return payment.status == Payment.Status.PENDING or (
        payment.status == Payment.Status.FAILED and payment.failure_reason == TIMEOUT_REASON)


def apply_result(payment, *, state, source, result_code=None, result_desc="", receipt=None, amount=None):
    """Move a locked payment to its final state and fulfil it. Caller holds select_for_update."""
    if not _can_accept_result(payment):
        return payment
    payload = dict(payment.provider_payload or {})
    payload.update({"result_code": result_code, "result_description": (result_desc or "")[:255], "result_source": source})
    now = timezone.now()
    if state == "success":
        if amount is not None and int(amount) != payment.amount:
            payment.status, payment.failure_reason = Payment.Status.DISPUTED, "amount_mismatch"
        else:
            payment.status, payment.failure_reason = Payment.Status.SUCCESSFUL, ""
            payment.completed_at = now
            if receipt:
                if Payment.objects.filter(provider_receipt=receipt).exclude(pk=payment.pk).exists():
                    payment.status, payment.failure_reason = Payment.Status.DISPUTED, "duplicate_receipt"
                    payment.completed_at = None
                else:
                    payment.provider_receipt = receipt
    elif state == "cancelled":
        payment.status, payment.failure_reason = Payment.Status.CANCELLED, "cancelled_by_payer"
    elif state == "failed":
        payment.status, payment.failure_reason = Payment.Status.FAILED, f"provider_{result_code}" if result_code is not None else "provider_failed"
    elif state == TIMEOUT_REASON:
        payment.status, payment.failure_reason = Payment.Status.FAILED, TIMEOUT_REASON
    else:
        return payment
    payment.provider_payload = payload
    payment.save(update_fields=("status", "failure_reason", "provider_receipt", "provider_payload", "completed_at", "updated_at"))
    _audit(None, f"payment.{payment.status}", payment, source=source, reason=payment.failure_reason, receipt=bool(payment.provider_receipt))
    if payment.status == Payment.Status.SUCCESSFUL:
        fulfil(payment)
    return payment


def fulfil(payment):
    """Grant what was paid for. Safe to call more than once."""
    from apps.accounts.models import TenantProfile
    from apps.properties.models import Property
    from apps.referrals.models import ReferralFee

    if payment.purpose == Payment.Purpose.VIEWING_CREDITS and payment.tenant_user_id and payment.credits:
        tenant = TenantProfile.objects.get_or_create(user_id=payment.tenant_user_id)[0]
        purchase, created = ViewingCreditPurchase.objects.get_or_create(
            payment=payment,
            defaults={"tenant": tenant, "credits_total": payment.credits, "credits_remaining": payment.credits,
                      "country": payment.package.country if payment.package_id else default_country()},
        )
        if created:
            notify(recipient=payment.tenant_user, event="payment.successful", dedupe_key=f"payment:{payment.pk}:successful",
                   title="Viewing package confirmed",
                   message=f"Payment of {payment.currency} {payment.amount:,} confirmed. {payment.credits} viewing credit{'s' if payment.credits != 1 else ''} added to your account.",
                   link="/tenant")
    elif payment.purpose == Payment.Purpose.REFERRAL_FEE and payment.fee_id:
        fee = ReferralFee.objects.select_for_update().get(pk=payment.fee_id)
        if fee.status != ReferralFee.Status.PAID:
            fee.status = ReferralFee.Status.PAID
            fee.paid_at = timezone.now()
            fee.save(update_fields=("status", "paid_at"))
            notify(recipient=fee.attribution.landlord.user, event="payment.successful", dedupe_key=f"payment:{payment.pk}:successful",
                   title="Success fee paid", message=f"Thank you. Your {payment.currency} {payment.amount:,} success fee has been received.",
                   link="/landlord?tab=payments")
    elif payment.purpose == Payment.Purpose.VERIFICATION_FEE and payment.property_id:
        prop = Property.objects.select_for_update().get(pk=payment.property_id)
        if prop.verification_status in (Property.VerificationStatus.UNVERIFIED, Property.VerificationStatus.REJECTED,
                                        Property.VerificationStatus.NEEDS_REVIEW):
            prop.verification_status = Property.VerificationStatus.PENDING
            prop.save(update_fields=("verification_status", "updated_at"))
            transaction.on_commit(_bust_public_cache)
        notify(recipient=prop.landlord.user, event="payment.successful", dedupe_key=f"payment:{payment.pk}:successful",
               title="Verification payment received",
               message=f"We received your verification payment for {prop.name}. Our team will review the property and let you know the outcome.",
               link="/landlord?tab=homes")


@transaction.atomic
def reconcile_payment(payment_id):
    """Query the provider for a pending (or timed-out) payment and apply the answer."""
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    if not _can_accept_result(payment):
        return payment
    timed_out = (payment.status == Payment.Status.PENDING
                 and timezone.now() - payment.created_at > timedelta(minutes=settings.PAYMENT_TIMEOUT_MINUTES))
    if payment.provider_reference.startswith("pending:"):
        # The STK prompt was never sent (e.g. the process died mid-request): nothing to query.
        return apply_result(payment, state=TIMEOUT_REASON, source="timeout") if timed_out else payment
    try:
        answer = get_provider().query(payment.provider_reference, payment)
    except MpesaError:
        answer = {"state": "pending", "result_code": None, "result_desc": "Provider unreachable"}
    if answer["state"] == "pending":
        return apply_result(payment, state=TIMEOUT_REASON, source="timeout") if timed_out else payment
    stored = (payment.provider_payload or {}).get("callback") or {}
    return apply_result(payment, state=answer["state"], source="query", result_code=answer["result_code"],
                        result_desc=answer["result_desc"], receipt=stored.get("receipt") or None, amount=stored.get("amount"))


def parse_callback(data):
    """Extract the fields we use from a Daraja STK callback body. Raises ValueError on bad input."""
    try:
        body = data["Body"]["stkCallback"]
        checkout_id = str(body["CheckoutRequestID"])
        result_code = int(body["ResultCode"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid callback") from exc
    items = body.get("CallbackMetadata", {}).get("Item", []) if isinstance(body.get("CallbackMetadata"), dict) else []
    metadata = {item.get("Name"): item.get("Value") for item in items if isinstance(item, dict)}
    receipt = str(metadata.get("MpesaReceiptNumber") or "")[:40] or None
    amount = metadata.get("Amount")
    return {"checkout_id": checkout_id, "result_code": result_code, "result_desc": str(body.get("ResultDesc", ""))[:255],
            "receipt": receipt, "amount": amount}


@transaction.atomic
def handle_callback(data):
    """Process a provider callback. Returns the payment, or None if it is unknown."""
    parsed = parse_callback(data)
    payment = Payment.objects.select_for_update().filter(provider_reference=parsed["checkout_id"]).first()
    if payment is None:
        return None
    if not _can_accept_result(payment):
        return payment  # duplicate or late callback for a settled payment: acknowledge, change nothing
    code = parsed["result_code"]
    payload = dict(payment.provider_payload or {})
    payload["callback"] = {"result_code": code, "receipt": parsed["receipt"],
                           "amount": parsed["amount"], "result_desc": parsed["result_desc"]}
    payment.provider_payload = payload
    payment.callback_received_at = timezone.now()
    payment.save(update_fields=("provider_payload", "callback_received_at", "updated_at"))

    if code != 0:
        state = "cancelled" if code == 1032 else "failed"
        return apply_result(payment, state=state, source="callback", result_code=code, result_desc=parsed["result_desc"])
    if not parsed["receipt"]:
        return apply_result(payment, state="failed", source="callback", result_code=code, result_desc="Missing receipt number")
    if settings.MPESA_CONFIRM_CALLBACKS:
        # Do not trust the callback body alone: confirm with Daraja before granting value.
        try:
            answer = get_provider().query(payment.provider_reference, payment)
        except MpesaError:
            answer = {"state": "pending"}
        if answer["state"] == "pending":
            return payment  # reconciliation will finish it using the stored callback data
        if answer["state"] != "success":
            payment.status, payment.failure_reason = Payment.Status.DISPUTED, "confirmation_mismatch"
            payment.save(update_fields=("status", "failure_reason", "updated_at"))
            _audit(None, "payment.disputed", payment, reason="confirmation_mismatch")
            return payment
    return apply_result(payment, state="success", source="callback", result_code=code,
                        result_desc=parsed["result_desc"], receipt=parsed["receipt"], amount=parsed["amount"])


def reconcile_stale_payments(limit=200):
    """Reconcile pending payments older than the query delay. Used by the cron command."""
    cutoff = timezone.now() - timedelta(seconds=settings.PAYMENT_QUERY_AFTER_SECONDS)
    ids = list(Payment.objects.filter(status=Payment.Status.PENDING, created_at__lt=cutoff)
               .order_by("created_at").values_list("pk", flat=True)[:limit])
    results = {}
    for payment_id in ids:
        status = reconcile_payment(payment_id).status
        results[status] = results.get(status, 0) + 1
    return results


# ---------------------------------------------------------------- refunds

@transaction.atomic
def record_refund(payment_id, *, admin, reason):
    """Record a refund made through the provider's portal and reverse what the payment granted.

    The platform does not push money back automatically (that needs M-Pesa B2C/reversal
    approval); an administrator refunds through Safaricom and records it here.
    """
    from apps.properties.models import Property
    from apps.referrals.models import ReferralFee

    payment = Payment.objects.select_for_update().get(pk=payment_id)
    if payment.status not in (Payment.Status.SUCCESSFUL, Payment.Status.DISPUTED):
        raise ValidationError("Only successful or disputed payments can be refunded.")
    metadata = {"reason": reason[:255], "previous_status": payment.status}
    if payment.purpose == Payment.Purpose.VIEWING_CREDITS:
        purchase = ViewingCreditPurchase.objects.select_for_update().filter(payment=payment).first()
        if purchase:
            if purchase.uses.filter(status=ViewingCreditUse.Status.RESERVED).exists():
                raise ValidationError("A credit from this package is reserved for an open viewing request. Resolve the request first.")
            metadata["credits_used"] = purchase.credits_total - purchase.credits_remaining
            metadata["credits_revoked"] = purchase.credits_remaining
            purchase.credits_remaining = 0
            purchase.save(update_fields=("credits_remaining",))
    elif payment.purpose == Payment.Purpose.REFERRAL_FEE and payment.fee_id:
        ReferralFee.objects.filter(pk=payment.fee_id).update(status=ReferralFee.Status.WAIVED)
    elif payment.purpose == Payment.Purpose.VERIFICATION_FEE and payment.property_id:
        Property.objects.filter(pk=payment.property_id, verification_status=Property.VerificationStatus.PENDING) \
            .update(verification_status=Property.VerificationStatus.UNVERIFIED, updated_at=timezone.now())
        transaction.on_commit(_bust_public_cache)
    payment.status = Payment.Status.REFUNDED
    payment.refunded_at = timezone.now()
    payment.refunded_by = admin
    payment.refund_reason = reason[:255]
    payment.save(update_fields=("status", "refunded_at", "refunded_by", "refund_reason", "updated_at"))
    _audit(admin, "payment.refunded", payment, **metadata)
    return payment
