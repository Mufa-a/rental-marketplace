from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.models import AuditLog
from .serializers import ReportSerializer


class ReportCreateView(APIView):
    """POST /api/v1/trust/reports/ — flag a listing as fraudulent, misleading or abusive.

    Reports are reviewed by administrators (see the admin dashboard's "Open reports"
    queue). The reporter's identity is stored but never shown to the reported party.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "report"

    def post(self, request):
        serializer = ReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing = serializer.validated_data["listing"]
        report = serializer.save(reporter=request.user, reported_user=listing.property.landlord.user)
        AuditLog.objects.create(actor=request.user, action="report.created", object_type=report._meta.label, object_id=str(report.pk))
        return Response({"id": report.pk, "message": "Thank you. Our team will review this report."}, status=201)
