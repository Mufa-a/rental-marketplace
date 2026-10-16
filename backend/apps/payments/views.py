import re
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import TenantProfile, User
from apps.accounts.serializers import normalize_phone
from apps.core.models import AuditLog
from apps.properties.models import Property
from apps.properties.views import _invalidate_public_listing_cache
from apps.referrals.models import ReferralFee
from .models import Payment, ViewingCreditPurchase
from .services import BUNDLES, MpesaError, initiate_stk_push, viewing_credit_balance


def initiate_referral_fee_push(payment_id, actor_id=None):
    """Send an already-recorded referral fee prompt after its transaction commits."""
    payment = Payment.objects.select_related("fee").get(pk=payment_id)
    if payment.status != Payment.Status.PENDING or not payment.fee_id:
        return
    try:
        result = initiate_stk_push(
            amount=payment.amount,
            phone=re.sub(r"\D", "", payment.phone_number),
            reference=str(payment.id),
        )
    except MpesaError as exc:
        payment.status = Payment.Status.FAILED
        payment.provider_payload = {"error": str(exc)}
        payment.save(update_fields=("status", "provider_payload", "updated_at"))
        return
    payment.provider_reference = result["CheckoutRequestID"]
    payment.provider_payload = {
        "merchant_request_id": result.get("MerchantRequestID"),
        "customer_message": result.get("CustomerMessage", ""),
    }
    payment.save(update_fields=("provider_reference", "provider_payload", "updated_at"))
    actor = User.objects.filter(pk=actor_id).first() if actor_id else None
    AuditLog.objects.create(actor=actor, action="payment.initiated", object_type=payment._meta.label, object_id=str(payment.pk))


class PaymentStartSerializer(serializers.Serializer):
    phone_number = serializers.RegexField(r"^(\+?254|0)[17]\d{8}$")
    idempotency_key = serializers.CharField(max_length=100, required=False)


class ViewingCreditPaymentSerializer(PaymentStartSerializer):
    credits = serializers.ChoiceField(choices=tuple(BUNDLES))


class ReferralFeePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, fee_id):
        fee = get_object_or_404(ReferralFee.objects.select_related("attribution__landlord__user"), pk=fee_id)
        if request.user.role != User.Role.ADMIN and fee.attribution.landlord.user_id != request.user.id:
            return Response({"error": {"code": "not_found", "message": "Fee not found."}}, status=404)
        if fee.status == ReferralFee.Status.PAID:
            return Response({"error": {"code": "already_paid", "message": "This fee has already been paid."}}, status=409)
        existing_payment = Payment.objects.filter(fee=fee, status=Payment.Status.PENDING).first()
        if existing_payment:
            return Response({"payment_id": existing_payment.id, "status": existing_payment.status, "provider_reference": existing_payment.provider_reference}, status=202)
        serializer = PaymentStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = serializer.validated_data.get("idempotency_key") or request.headers.get("Idempotency-Key") or uuid4().hex
        phone = normalize_phone(serializer.validated_data["phone_number"])
        payment, created = Payment.objects.get_or_create(
            idempotency_key=key,
            defaults={"fee": fee, "purpose": Payment.Purpose.REFERRAL_FEE, "amount": fee.amount, "phone_number": phone,
                      "provider_reference": f"pending:{uuid4().hex}"},
        )
        if payment.fee_id != fee.id:
            return Response({"error": {"code": "idempotency_conflict", "message": "That idempotency key was used for another fee."}}, status=409)
        if not created:
            return Response({"payment_id": payment.id, "status": payment.status, "provider_reference": payment.provider_reference})
        initiate_referral_fee_push(payment.pk, request.user.pk)
        payment.refresh_from_db()
        if payment.status == Payment.Status.FAILED:
            return Response({"error": {"code": "payment_provider_error", "message": payment.provider_payload.get("error", "M-Pesa did not accept the prompt.")}}, status=503)
        return Response({"payment_id": payment.id, "status": payment.status, "message": payment.provider_payload.get("customer_message") or "Check your phone to complete payment."}, status=202)


class ViewingCreditWalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != User.Role.TENANT:
            return Response({"error": {"code": "tenant_only", "message": "Viewing bundles are for tenant accounts."}}, status=403)
        tenant = TenantProfile.objects.get_or_create(user=request.user)[0]
        return Response({
            "balance": viewing_credit_balance(tenant),
            "bundles": [{"credits": credits, "price": price} for credits, price in BUNDLES.items()],
        })

    @transaction.atomic
    def post(self, request):
        if request.user.role != User.Role.TENANT:
            return Response({"error": {"code": "tenant_only", "message": "Viewing bundles are for tenant accounts."}}, status=403)
        serializer = ViewingCreditPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credits = int(serializer.validated_data["credits"])
        phone = normalize_phone(serializer.validated_data["phone_number"])
        pending = Payment.objects.filter(
            purpose=Payment.Purpose.VIEWING_CREDITS,
            tenant_user=request.user,
            status=Payment.Status.PENDING,
        ).first()
        if pending:
            return Response({"error": {"code": "bundle_payment_pending", "message": "Approve or wait for your current M-Pesa bundle prompt before starting another."}}, status=409)
        key = serializer.validated_data.get("idempotency_key") or request.headers.get("Idempotency-Key") or uuid4().hex
        payment, created = Payment.objects.get_or_create(
            idempotency_key=key,
            defaults={
                "fee": None, "purpose": Payment.Purpose.VIEWING_CREDITS,
                "tenant_user": request.user, "credits": credits, "amount": BUNDLES[credits],
                "phone_number": phone, "provider_reference": f"pending:{uuid4().hex}",
            },
        )
        if (payment.purpose != Payment.Purpose.VIEWING_CREDITS or payment.tenant_user_id != request.user.id
                or payment.credits != credits or payment.amount != BUNDLES[credits]):
            return Response({"error": {"code": "idempotency_conflict", "message": "That payment key was used for a different purchase."}}, status=409)
        if not created:
            return Response({"payment_id": payment.id, "status": payment.status, "message": "This bundle payment already exists."}, status=202)
        try:
            result = initiate_stk_push(amount=payment.amount, phone=re.sub(r"\D", "", phone), reference=f"vc{payment.id}")
        except MpesaError as exc:
            payment.status = Payment.Status.FAILED
            payment.provider_payload = {"error": str(exc)}
            payment.save(update_fields=("status", "provider_payload", "updated_at"))
            return Response({"error": {"code": "payment_provider_error", "message": str(exc)}}, status=503)
        payment.provider_reference = result["CheckoutRequestID"]
        payment.provider_payload = {"merchant_request_id": result.get("MerchantRequestID"), "customer_message": result.get("CustomerMessage", "")}
        payment.save(update_fields=("provider_reference", "provider_payload", "updated_at"))
        AuditLog.objects.create(actor=request.user, action="viewing_credits.payment_initiated", object_type=payment._meta.label, object_id=str(payment.pk))
        return Response({"payment_id": payment.id, "status": payment.status, "message": result.get("CustomerMessage", "Check your phone to complete payment.")}, status=202)


VERIFICATION_FEE = 2000


class PropertyVerificationPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, property_id):
        prop = get_object_or_404(Property.objects.select_for_update().select_related("landlord__user"), pk=property_id)
        if request.user.role != User.Role.ADMIN and prop.landlord.user_id != request.user.id:
            return Response({"error": {"code": "not_found", "message": "Property not found."}}, status=404)
        verification = Property.VerificationStatus
        if prop.verification_status == verification.VERIFIED:
            return Response({"error": {"code": "already_verified", "message": "This property is already verified."}}, status=409)
        if prop.verification_status == verification.PENDING:
            return Response({"error": {"code": "review_pending", "message": "Payment received. This property is awaiting review."}}, status=409)
        if Payment.objects.filter(property=prop, purpose=Payment.Purpose.VERIFICATION_FEE, status=Payment.Status.PENDING).exists():
            return Response({"error": {"code": "payment_pending", "message": "Approve or wait for your current M-Pesa prompt before starting another."}}, status=409)
        if prop.verification_status == verification.REJECTED and Payment.objects.filter(
            property=prop, purpose=Payment.Purpose.VERIFICATION_FEE, status=Payment.Status.SUCCESSFUL
        ).exists():
            prop.verification_status = verification.PENDING
            prop.save(update_fields=("verification_status", "updated_at"))
            transaction.on_commit(_invalidate_public_listing_cache)
            return Response({"status": "pending", "message": "Resubmitted for review. You were not charged again."})

        serializer = PaymentStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = normalize_phone(serializer.validated_data["phone_number"])
        key = serializer.validated_data.get("idempotency_key") or request.headers.get("Idempotency-Key") or uuid4().hex
        payment, created = Payment.objects.get_or_create(
            idempotency_key=key,
            defaults={
                "fee": None, "property": prop, "purpose": Payment.Purpose.VERIFICATION_FEE,
                "amount": VERIFICATION_FEE, "phone_number": phone,
                "provider_reference": f"pending:{uuid4().hex}",
            },
        )
        if payment.property_id != prop.id or payment.purpose != Payment.Purpose.VERIFICATION_FEE:
            return Response({"error": {"code": "idempotency_conflict", "message": "That payment key was used for something else."}}, status=409)
        if not created:
            return Response({"payment_id": payment.id, "status": payment.status, "message": "This payment already exists."}, status=202)
        try:
            result = initiate_stk_push(amount=payment.amount, phone=re.sub(r"\D", "", phone), reference=f"vf{payment.id}")
        except MpesaError as exc:
            payment.status = Payment.Status.FAILED
            payment.provider_payload = {"error": str(exc)}
            payment.save(update_fields=("status", "provider_payload", "updated_at"))
            return Response({"error": {"code": "payment_provider_error", "message": str(exc)}}, status=503)
        payment.provider_reference = result["CheckoutRequestID"]
        payment.provider_payload = {"merchant_request_id": result.get("MerchantRequestID"), "customer_message": result.get("CustomerMessage", "")}
        payment.save(update_fields=("provider_reference", "provider_payload", "updated_at"))
        AuditLog.objects.create(actor=request.user, action="property_verification.payment_initiated", object_type=payment._meta.label, object_id=str(payment.pk))
        return Response({"payment_id": payment.id, "status": payment.status, "message": result.get("CustomerMessage", "Check your phone to complete payment.")}, status=202)


class MpesaCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @transaction.atomic
    def post(self, request, callback_token):
        if not settings.MPESA_CALLBACK_TOKEN or callback_token != settings.MPESA_CALLBACK_TOKEN:
            return Response({"ResultCode": 1, "ResultDesc": "Invalid callback token"}, status=404)
        try:
            body = request.data["Body"]["stkCallback"]
            checkout_id = body["CheckoutRequestID"]
            result_code = int(body["ResultCode"])
        except (KeyError, TypeError, ValueError):
            return Response({"ResultCode": 1, "ResultDesc": "Invalid callback"}, status=400)
        payment = get_object_or_404(Payment.objects.select_for_update(), provider_reference=checkout_id)
        if payment.status != Payment.Status.PENDING:
            return Response({"ResultCode": 0, "ResultDesc": "Callback already processed"})
        metadata = {item.get("Name"): item.get("Value") for item in body.get("CallbackMetadata", {}).get("Item", []) if isinstance(item, dict)}
        safe_result = {"result_code": result_code, "result_description": body.get("ResultDesc", "")[:255]}
        if result_code == 0:
            try:
                if int(metadata.get("Amount", 0)) != payment.amount:
                    raise ValueError("Payment amount did not match")
                receipt = str(metadata.get("MpesaReceiptNumber", ""))
                if not receipt:
                    raise ValueError("Missing receipt number")
            except (TypeError, ValueError):
                payment.status = Payment.Status.DISPUTED
            else:
                payment.status = Payment.Status.SUCCESSFUL
                if payment.purpose == Payment.Purpose.REFERRAL_FEE and payment.fee_id:
                    payment.fee.status = ReferralFee.Status.PAID
                    payment.fee.save(update_fields=("status",))
                elif payment.purpose == Payment.Purpose.VIEWING_CREDITS and payment.tenant_user_id and payment.credits:
                    tenant = TenantProfile.objects.get_or_create(user_id=payment.tenant_user_id)[0]
                    ViewingCreditPurchase.objects.get_or_create(
                        payment=payment,
                        defaults={"tenant": tenant, "credits_total": payment.credits, "credits_remaining": payment.credits},
                    )
                elif payment.purpose == Payment.Purpose.VERIFICATION_FEE and payment.property_id:
                    prop = payment.property
                    if prop.verification_status in (Property.VerificationStatus.UNVERIFIED, Property.VerificationStatus.REJECTED):
                        prop.verification_status = Property.VerificationStatus.PENDING
                        prop.save(update_fields=("verification_status", "updated_at"))
                        transaction.on_commit(_invalidate_public_listing_cache)
                else:
                    payment.status = Payment.Status.DISPUTED
                safe_result["receipt"] = receipt
        else:
            payment.status = Payment.Status.FAILED
        payment.provider_payload = safe_result
        payment.save(update_fields=("status", "provider_payload", "updated_at"))
        AuditLog.objects.create(actor=None, action=f"payment.{payment.status}", object_type=payment._meta.label, object_id=str(payment.pk))
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})
