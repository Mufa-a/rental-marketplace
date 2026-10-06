from django.db import IntegrityError, transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.models import AuditLog
from . import services
from .models import Report
from .serializers import ReportSerializer


def _error(code, message, status):
    return Response({"error": {"code": code, "message": message}}, status=status)


class ReportCreateView(APIView):
    """POST /api/v1/trust/reports/ — flag a listing as fraudulent, misleading or abusive.

    Reports are reviewed by administrators (see the admin dashboard's "Open reports"
    queue). The reporter's identity is stored but never shown to the reported party.
    One open report per person per listing; once enough different people report the same
    listing for a serious reason it is taken offline for review (see services.maybe_auto_hide).
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "report"

    def post(self, request):
        serializer = ReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing = serializer.validated_data["listing"]
        landlord_user = listing.property.landlord.user

        if landlord_user.pk == request.user.pk:
            return _error("own_listing", "You cannot report your own listing.", 400)
        if Report.objects.filter(reporter=request.user, listing=listing, resolved_at__isnull=True).exists():
            return _error("already_reported", "You have already reported this listing. Our team is reviewing it.", 409)

        try:
            with transaction.atomic():
                report = serializer.save(reporter=request.user, reported_user=landlord_user)
                AuditLog.objects.create(actor=request.user, action="report.created", object_type=report._meta.label, object_id=str(report.pk))
                services.maybe_auto_hide(listing)
        except IntegrityError:  # two identical requests raced past the check above
            return _error("already_reported", "You have already reported this listing. Our team is reviewing it.", 409)
        return Response({"id": report.pk, "message": "Thank you. Our team will review this report."}, status=201)
