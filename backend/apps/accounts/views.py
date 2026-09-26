import logging

from django.shortcuts import get_object_or_404
from django.contrib.auth.hashers import make_password
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from . import services
from .models import User
from .serializers import OTPRequestSerializer, OTPVerifySerializer, ProfileSerializer
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
        phone_number = serializer.validated_data["phone_number"]
        role = serializer.validated_data.get("role")

        user, created = User.objects.get_or_create(
            phone_number=phone_number,
            defaults={
                "username": phone_number,
                "role": role or User.Role.TENANT,
                "is_active": False,
                "password": make_password(None),
            },
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

        user = get_object_or_404(User, phone_number=phone_number)

        try:
            services.verify_otp(user, code)
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
