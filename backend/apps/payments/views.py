import hmac
import ipaddress
import logging
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import TenantProfile, User
from apps.accounts.serializers import normalize_phone, phone_validator
from apps.core.permissions import is_platform_admin
from apps.properties.models import Property
from apps.referrals.models import ReferralFee

from . import services
from .models import Payment, ReferralFeeRule, ServicePrice, ViewingPackage
from .providers import MpesaError

logger = logging.getLogger(__name__)

# Shown to tenants before they pay, and mirrored in the Terms (section "Viewing packages").
PACKAGE_CONDITIONS = [
    "Browsing and saving homes is free. A package buys viewing-request credits; it is not rent, a deposit or a booking fee.",
    "One credit is set aside when you send a viewing request and is used only when the landlord approves the viewing.",
    "The credit comes back automatically if the landlord declines, the request expires unanswered, you cancel before approval, or the landlord cancels an approved viewing.",
    "Credits do not expire and can be used for any listing in the same country.",
    "Never pay a landlord or agent to secure a viewing. Rent and deposits are agreed directly with the landlord after you have seen the home.",
    "Refunds for unused credits are handled under the refund policy on the Terms page.",
]


class PackageSerializer(serializers.ModelSerializer):
    price_per_viewing = serializers.SerializerMethodField()

    class Meta:
        model = ViewingPackage
        fields = ("id", "name", "description", "credits", "price", "currency", "price_per_viewing")

    def get_price_per_viewing(self, obj):
        return round(obj.price / obj.credits, 2)


class FeeRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralFeeRule
        fields = ("min_rent", "max_rent", "fee_type", "amount", "percent", "currency")


class PaymentSerializer(serializers.ModelSerializer):
    message = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ("id", "purpose", "status", "amount", "currency", "credits", "failure_reason", "provider_receipt",
                  "message", "created_at", "completed_at", "refunded_at")

    def get_message(self, obj):
        if obj.status == Payment.Status.PENDING:
            return (obj.provider_payload or {}).get("customer_message") or "Check your phone and enter your M-Pesa PIN to approve the payment."
        if obj.status == Payment.Status.SUCCESSFUL:
            return "Payment confirmed by M-Pesa."
        if obj.status == Payment.Status.CANCELLED:
            return "You cancelled the M-Pesa prompt. You were not charged."
        if obj.status == Payment.Status.FAILED:
            if obj.failure_reason == services.TIMEOUT_REASON:
                return "We did not receive a confirmation from M-Pesa in time. If money left your account, it will be matched automatically or contact support with your M-Pesa message."
            return "The payment did not go through. You were not charged; you can try again."
        if obj.status == Payment.Status.REFUNDED:
            return "This payment was refunded."
        return "This payment needs a manual check by our team. We will contact you."


def _phone_and_key(request, data):
    phone = normalize_phone(data["phone_number"])
    key = data.get("idempotency_key") or request.headers.get("Idempotency-Key") or uuid4().hex
    # Scope keys per user so one account can never collide with (or probe) another's payment.
    return phone, f"u{request.user.pk}:{key}"[:100]


def _provider_error(exc):
    return Response({"error": {"code": "payment_provider_error", "message": str(exc)}}, status=503)


def _started(payment, created):
    data = PaymentSerializer(payment).data
    data["payment_id"] = payment.pk  # kept for older clients
    return Response(data, status=202 if created or payment.status == Payment.Status.PENDING else 200)


class PaymentStartSerializer(serializers.Serializer):
    phone_number = serializers.CharField(validators=[phone_validator])
    idempotency_key = serializers.CharField(max_length=64, required=False)


class ViewingCreditPaymentSerializer(PaymentStartSerializer):
    package_id = serializers.IntegerField(required=False)
    credits = serializers.IntegerField(required=False, min_value=1)  # legacy clients chose by size

    def validate(self, attrs):
        if not attrs.get("package_id") and not attrs.get("credits"):
            raise serializers.ValidationError("Choose a viewing package.")
        return attrs


class PriceListView(APIView):
    """GET /payments/prices/?country=KE — public, so everyone can see what things cost before signing up."""

    permission_classes = [AllowAny]

    def get(self, request):
        country = (request.query_params.get("country") or settings.DEFAULT_COUNTRY).upper()[:2]
        verification = ServicePrice.objects.filter(country=country, code=ServicePrice.Code.PROPERTY_VERIFICATION, is_active=True).first()
        return Response({
            "country": country,
            "viewing_packages": PackageSerializer(services.active_packages(country), many=True).data,
            "package_conditions": PACKAGE_CONDITIONS,
            "referral_fee_rules": FeeRuleSerializer(ReferralFeeRule.objects.filter(country=country, is_active=True), many=True).data,
            "property_verification_fee": {"amount": verification.amount, "currency": verification.currency} if verification else None,
        })


class ViewingCreditWalletView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "payment_start"

    def get_throttles(self):
        return [ScopedRateThrottle()] if self.request.method == "POST" else []

    def _tenant(self, request):
        if request.user.role != User.Role.TENANT:
            raise PermissionDenied("Viewing packages are for tenant accounts.")
        return TenantProfile.objects.get_or_create(user=request.user)[0]

    def get(self, request):
        tenant = self._tenant(request)
        packages = services.active_packages()
        pending = Payment.objects.filter(purpose=Payment.Purpose.VIEWING_CREDITS, tenant_user=request.user, status=Payment.Status.PENDING).order_by("-created_at").first()
        if pending:
            pending = services.reconcile_if_stale(pending)
        return Response({
            "balance": services.viewing_credit_balance(tenant),
            "packages": PackageSerializer(packages, many=True).data,
            "bundles": [{"credits": p.credits, "price": p.price, "package_id": p.pk} for p in packages],
            "conditions": PACKAGE_CONDITIONS,
            "pending_payment": PaymentSerializer(pending).data if pending and pending.status == Payment.Status.PENDING else None,
        })

    def post(self, request):
        self._tenant(request)
        serializer = ViewingCreditPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        packages = services.active_packages()
        package = packages.filter(pk=data["package_id"]).first() if data.get("package_id") else packages.filter(credits=data["credits"]).first()
        if package is None:
            raise ValidationError({"package_id": "That viewing package is not available."})
        phone, key = _phone_and_key(request, data)
        existing = Payment.objects.filter(idempotency_key=key).first()
        if existing is None:
            blocking = services.blocking_pending(Payment.objects.filter(purpose=Payment.Purpose.VIEWING_CREDITS, tenant_user=request.user))
            if blocking:
                return Response({"error": {"code": "bundle_payment_pending",
                                           "message": "Approve or cancel the M-Pesa prompt already on your phone, then try again in a minute."},
                                 "payment": PaymentSerializer(blocking).data}, status=409)
        try:
            payment, created = services.start_payment(
                actor=request.user, purpose=Payment.Purpose.VIEWING_CREDITS, amount=package.price, phone=phone,
                idempotency_key=key, reference="NYV{id}", description="Viewing pack",
                tenant_user=request.user, package=package, credits=package.credits,
            )
        except MpesaError as exc:
            return _provider_error(exc)
        return _started(payment, created)


class PaymentDetailView(APIView):
    """GET /payments/<id>/ — the payer polls this after the STK prompt. Reconciles stale payments."""

    permission_classes = [IsAuthenticated]

    def get(self, request, payment_id):
        payment = get_object_or_404(Payment.objects.select_related("fee__attribution__landlord", "property__landlord"), pk=payment_id)
        owner_ids = {payment.tenant_user_id,
                     payment.fee.attribution.landlord.user_id if payment.fee_id else None,
                     payment.property.landlord.user_id if payment.property_id else None}
        if request.user.pk not in owner_ids and not is_platform_admin(request.user):
            return Response({"error": {"code": "not_found", "message": "Payment not found."}}, status=404)
        return Response(PaymentSerializer(services.reconcile_if_stale(payment)).data)


class MyPaymentListView(APIView):
    """GET /payments/mine/ — the signed-in user's own payment history."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Q
        payments = Payment.objects.filter(
            Q(tenant_user=request.user) | Q(fee__attribution__landlord__user=request.user) | Q(property__landlord__user=request.user)
        ).order_by("-created_at")[:100]
        return Response(PaymentSerializer(payments, many=True).data)


class ReferralFeePaymentView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "payment_start"

    def post(self, request, fee_id):
        fee = get_object_or_404(ReferralFee.objects.select_related("attribution__landlord__user"), pk=fee_id)
        if fee.attribution.landlord.user_id != request.user.id:
            return Response({"error": {"code": "not_found", "message": "Fee not found."}}, status=404)
        if fee.status != ReferralFee.Status.PENDING:
            return Response({"error": {"code": "not_payable", "message": "This fee is not awaiting payment."}}, status=409)
        blocking = services.blocking_pending(Payment.objects.filter(fee=fee))
        if blocking:
            return _started(blocking, False)
        serializer = PaymentStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone, key = _phone_and_key(request, serializer.validated_data)
        try:
            payment, created = services.start_payment(
                actor=request.user, purpose=Payment.Purpose.REFERRAL_FEE, amount=fee.amount, phone=phone,
                idempotency_key=key, reference="NYF{id}", description="Success fee", fee=fee,
            )
        except MpesaError as exc:
            return _provider_error(exc)
        return _started(payment, created)


class PropertyVerificationPaymentView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "payment_start"

    def post(self, request, property_id):
        with transaction.atomic():
            prop = get_object_or_404(Property.objects.select_for_update().select_related("landlord__user"), pk=property_id)
            if prop.landlord.user_id != request.user.id:
                return Response({"error": {"code": "not_found", "message": "Property not found."}}, status=404)
            status_ = Property.VerificationStatus
            if prop.verification_status == status_.VERIFIED:
                return Response({"error": {"code": "already_verified", "message": "This property is already verified."}}, status=409)
            if prop.verification_status == status_.PENDING:
                return Response({"error": {"code": "review_pending", "message": "Payment received. This property is awaiting review."}}, status=409)
            if prop.verification_status in (status_.REJECTED, status_.NEEDS_REVIEW) and Payment.objects.filter(
                property=prop, purpose=Payment.Purpose.VERIFICATION_FEE, status=Payment.Status.SUCCESSFUL
            ).exists():
                prop.verification_status = status_.PENDING
                prop.save(update_fields=("verification_status", "updated_at"))
                transaction.on_commit(services._bust_public_cache)
                return Response({"status": "pending", "message": "Resubmitted for review. You were not charged again."})
        blocking = services.blocking_pending(Payment.objects.filter(property=prop, purpose=Payment.Purpose.VERIFICATION_FEE))
        if blocking:
            return _started(blocking, False)
        serializer = PaymentStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        price = services.service_price(ServicePrice.Code.PROPERTY_VERIFICATION, prop.country)
        phone, key = _phone_and_key(request, serializer.validated_data)
        try:
            payment, created = services.start_payment(
                actor=request.user, purpose=Payment.Purpose.VERIFICATION_FEE, amount=price.amount, phone=phone,
                idempotency_key=key, reference="NYP{id}", description="Verification", property=prop,
            )
        except MpesaError as exc:
            return _provider_error(exc)
        return _started(payment, created)


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    proxies = settings.REST_FRAMEWORK.get("NUM_PROXIES") or 0
    if forwarded and proxies:
        hops = [part.strip() for part in forwarded.split(",")]
        return hops[-min(proxies, len(hops))]
    return request.META.get("REMOTE_ADDR", "")


def _ip_allowed(request):
    allowed = settings.MPESA_CALLBACK_ALLOWED_IPS
    if not allowed:
        return True
    try:
        ip = ipaddress.ip_address(_client_ip(request))
    except ValueError:
        return False
    return any(ip in ipaddress.ip_network(net, strict=False) for net in allowed)


class MpesaCallbackView(APIView):
    """Safaricom posts STK results here. Authenticated by a secret path token (and optional IP allowlist);
    success is additionally confirmed with an STK Push Query before any value is granted."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, callback_token):
        expected = settings.MPESA_CALLBACK_TOKEN
        if not expected or not hmac.compare_digest(callback_token.encode(), expected.encode()) or not _ip_allowed(request):
            return Response({"ResultCode": 1, "ResultDesc": "Rejected"}, status=404)
        try:
            payment = services.handle_callback(request.data)
        except ValueError:
            return Response({"ResultCode": 1, "ResultDesc": "Invalid callback"}, status=400)
        if payment is None:
            logger.warning("M-Pesa callback for an unknown checkout request")
            return Response({"ResultCode": 0, "ResultDesc": "Unknown request"})
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})
