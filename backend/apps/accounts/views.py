import logging

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from . import services
from apps.core.models import AuditLog
from .models import AccountDeletionRequest, ConsentRecord, User
from .serializers import ConsentSerializer, DeletionRequestSerializer, OTPRequestSerializer, OTPVerifySerializer, ProfileSerializer
from .throttles import PhoneOTPThrottle

logger = logging.getLogger(__name__)


class OTPRequestView(APIView):
    """
    POST /api/v1/auth/otp/request/
    {"phone_number": "0712345678", "role": "tenant"}

    One endpoint for both signup and login — creates the user on first
    request (inactive until verified) and sends an OTP either way. The
    phone number is the only identity that matters; there's no separate
    "register" step to fall out of sync with this one.
    """

    permission_classes = [AllowAny]
    throttle_classes = [PhoneOTPThrottle]

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        phone_number = data["phone_number"]
        role = data.get("role")

        user = User.objects.filter(phone_number=phone_number).first()
        created = user is None
        if created:
            # Creating an account requires agreeing to the Terms and acknowledging the
            # Privacy Policy. Marketing consent is separate and optional.
            if not data["accept_terms"]:
                return Response(
                    {"error": {"code": "terms_required", "message": "Please agree to the Terms & Conditions and acknowledge the Privacy Policy to create an account."}},
                    status=400,
                )
            version = data.get("policy_version") or settings.LEGAL_POLICY_VERSION
            try:
                with transaction.atomic():
                    user = User.objects.create(
                        phone_number=phone_number, username=phone_number,
                        role=role or User.Role.TENANT, is_active=False, password=make_password(None),
                    )
                    ConsentRecord.objects.create(user=user, consent_type=ConsentRecord.ConsentType.TERMS_PRIVACY, granted=True, policy_version=version)
                    if data["marketing_opt_in"]:
                        ConsentRecord.objects.create(user=user, consent_type=ConsentRecord.ConsentType.MARKETING, granted=True, policy_version=version)
            except IntegrityError:
                # Two signups for the same number raced; use the account that won.
                user, created = User.objects.get(phone_number=phone_number), False
        elif user.phone_verified and not user.is_active:
            return Response(
                {"error": {"code": "account_unavailable", "message": "This account is not available. Please contact support."}},
                status=403,
            )

        try:
            services.send_otp(user)
        except services.OTPLocked as exc:
            return Response({"error": {"code": "otp_locked", "message": str(exc)}}, status=429)
        except Exception:
            logger.exception("OTP delivery failed for user id %s", user.pk)
            return Response(
                {"error": {"code": "otp_delivery_failed", "message": "We could not send a verification code. Please try again later."}},
                status=503,
            )

        return Response(
            {
                "phone_number": phone_number,
                "new_account": created,
                "expires_in_minutes": services.OTP_TTL_MINUTES,
            }
        )


class OTPVerifyView(APIView):
    """
    POST /api/v1/auth/otp/verify/
    {"phone_number": "0712345678", "code": "123456"}

    Verifies the code, activates the account, marks the phone verified,
    and issues a JWT access/refresh pair. This confirms signup and logs
    the user in, in one call.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"]
        code = serializer.validated_data["code"]

        user = User.objects.filter(phone_number=phone_number).first()
        if user is None:
            # Same response as a wrong code so this endpoint cannot be used to
            # discover which phone numbers have accounts.
            return Response({"error": {"code": "otp_invalid", "message": "Incorrect code."}}, status=400)

        try:
            services.verify_otp(user, code)
        except services.AccountSuspended as exc:
            return Response({"error": {"code": "account_unavailable", "message": "This account is not available. Please contact support."}}, status=403)
        except services.OTPLocked as exc:
            return Response({"error": {"code": "otp_locked", "message": str(exc)}}, status=429)
        except services.OTPInvalid as exc:
            return Response({"error": {"code": "otp_invalid", "message": str(exc)}}, status=400)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {"id": user.id, "phone_number": user.phone_number, "role": user.role},
            }
        )


class LogoutView(APIView):
    """POST /api/v1/auth/logout/ {"refresh": "..."} — blacklists the refresh token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh = RefreshToken(request.data.get("refresh", ""))
            if str(refresh.get("user_id")) != str(request.user.pk):
                return Response(
                    {"error": {"code": "invalid_token", "message": "This refresh token does not belong to your account."}},
                    status=400,
                )
            refresh.blacklist()
        except (TokenError, KeyError, TypeError):
            return Response(
                {"error": {"code": "invalid_token", "message": "Invalid or already blacklisted."}},
                status=400,
            )
        return Response(status=204)


class MeView(APIView):
    """GET /api/v1/auth/me/ — proves JWT auth works end to end; the frontend's session check."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ProfileSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ConsentView(APIView):
    """GET /auth/consents/ — current consent state; POST — record a grant or withdrawal."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        latest = {}
        for record in ConsentRecord.objects.filter(user=request.user).order_by("created_at", "id"):
            latest[record.consent_type] = record
        return Response([
            {"consent_type": kind, "granted": record.granted, "policy_version": record.policy_version, "recorded_at": record.created_at}
            for kind, record in latest.items()
        ])

    def post(self, request):
        serializer = ConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        record = ConsentRecord.objects.create(
            user=request.user, consent_type=data["consent_type"], granted=data["granted"],
            policy_version=data.get("policy_version") or settings.LEGAL_POLICY_VERSION,
        )
        return Response(
            {"consent_type": record.consent_type, "granted": record.granted, "policy_version": record.policy_version, "recorded_at": record.created_at},
            status=201,
        )


def _deletion_context(user):
    """What a person should know before asking for deletion. Counts come from the database."""
    from apps.referrals.models import ReferralFee
    from apps.viewings.models import ViewingRequest

    active_statuses = [ViewingRequest.Status.PENDING, ViewingRequest.Status.APPROVED]
    warnings = []
    if user.role == User.Role.TENANT:
        active = ViewingRequest.objects.filter(tenant__user=user, status__in=active_statuses).count()
        if active:
            warnings.append(f"You have {active} active viewing request(s). They will be cancelled if your account is deleted.")
    elif user.role == User.Role.LANDLORD:
        active = ViewingRequest.objects.filter(unit__property__landlord__user=user, status__in=active_statuses).count()
        if active:
            warnings.append(f"You have {active} active viewing request(s) from tenants that will be closed.")
        unpaid = ReferralFee.objects.filter(attribution__landlord__user=user, status=ReferralFee.Status.PENDING).count()
        if unpaid:
            warnings.append(f"You have {unpaid} unpaid success fee(s). Fee and payment records must be kept and the fees remain due.")
    return {
        "will_happen": [
            "Your request is reviewed by an administrator before anything is deleted; it is not instant.",
            "Your profile details and sign-in access will be removed or anonymised once the request is approved.",
            "Any listings you published will be taken down.",
        ],
        "may_be_retained": [
            "Payment and fee records, and audit logs of viewing requests and outcomes, may need to be kept for accounting, fraud-prevention or legal reasons.",
            "The specific retention periods are set by the platform owner and are not yet published here.",
        ],
        "warnings": warnings,
    }


class DeletionRequestView(APIView):
    """
    GET    /auth/deletion-request/  — current request (if any) plus what deletion involves
    POST   /auth/deletion-request/  {"confirm_phone": "...", "reason": "..."} — file a request
    DELETE /auth/deletion-request/  — cancel a pending request
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "deletion_request"

    def get_throttles(self):
        from rest_framework.throttling import ScopedRateThrottle
        return [ScopedRateThrottle()] if self.request.method == "POST" else []

    def get(self, request):
        current = AccountDeletionRequest.objects.filter(user=request.user).order_by("-requested_at").first()
        return Response({
            "request": None if current is None else {
                "status": current.status, "requested_at": current.requested_at, "resolved_at": current.resolved_at,
            },
            **_deletion_context(request.user),
        })

    def post(self, request):
        if request.user.role == User.Role.ADMIN:
            return Response({"error": {"code": "not_allowed", "message": "Administrator accounts are removed by another administrator."}}, status=403)
        serializer = DeletionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["confirm_phone"] != request.user.phone_number:
            return Response({"error": {"code": "confirmation_mismatch", "message": "That phone number does not match your account."}}, status=400)
        if AccountDeletionRequest.objects.filter(user=request.user, status=AccountDeletionRequest.Status.PENDING).exists():
            return Response({"error": {"code": "already_requested", "message": "You already have a deletion request waiting for review."}}, status=409)
        deletion = AccountDeletionRequest.objects.create(
            user=request.user, phone_last4=request.user.phone_number[-4:], role=request.user.role,
            reason=serializer.validated_data.get("reason", ""),
        )
        AuditLog.objects.create(actor=request.user, action="account.deletion_requested", object_type=deletion._meta.label, object_id=str(deletion.pk))
        return Response({"status": deletion.status, "requested_at": deletion.requested_at, **_deletion_context(request.user)}, status=201)

    def delete(self, request):
        deletion = AccountDeletionRequest.objects.filter(user=request.user, status=AccountDeletionRequest.Status.PENDING).first()
        if deletion is None:
            return Response({"error": {"code": "not_found", "message": "You have no pending deletion request."}}, status=404)
        deletion.status = AccountDeletionRequest.Status.CANCELLED
        deletion.resolved_at = timezone.now()
        deletion.save(update_fields=["status", "resolved_at"])
        AuditLog.objects.create(actor=request.user, action="account.deletion_cancelled", object_type=deletion._meta.label, object_id=str(deletion.pk))
        return Response(status=204)
