from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import LandlordProfile, User

from . import services
from .models import LandlordVerification, VerificationDocument

DISCLAIMER = ("Verification means our team checked the landlord's identity documents and stated relationship to the "
              "property. It is not a guarantee that a landlord or home is legitimate. Never pay before viewing.")


class SubmissionSerializer(serializers.ModelSerializer):
    id_number = serializers.CharField(write_only=True, min_length=4, max_length=30)

    class Meta:
        model = LandlordVerification
        fields = ("legal_name", "id_type", "id_number", "relationship", "agency_name")

    def validate(self, attrs):
        number = "".join(ch for ch in attrs.pop("id_number") if ch.isalnum())
        if len(number) < 4:
            raise serializers.ValidationError({"id_number": "Enter the full document number."})
        attrs["id_last4"] = number[-4:].upper()  # the full number is never stored
        return attrs


class StatusSerializer(serializers.ModelSerializer):
    documents = serializers.SerializerMethodField()

    class Meta:
        model = LandlordVerification
        fields = ("id", "status", "legal_name", "id_type", "id_last4", "relationship", "agency_name",
                  "submitted_at", "reviewed_at", "reviewer_note", "documents")

    def get_documents(self, obj):
        return [{"kind": d.kind, "label": d.get_kind_display()} for d in obj.documents.all()]


class LandlordVerificationView(APIView):
    """GET your verification status; POST (multipart) a new submission."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "verification_upload"

    def get_throttles(self):
        return [ScopedRateThrottle()] if self.request.method == "POST" else []

    def _landlord(self, request):
        if request.user.role != User.Role.LANDLORD:
            raise PermissionDenied("Verification is for landlord accounts.")
        return LandlordProfile.objects.get_or_create(user=request.user)[0]

    def get(self, request):
        landlord = self._landlord(request)
        latest = landlord.verifications.prefetch_related("documents").first()
        return Response({
            "verified": landlord.verification_tier in ("standard", "trusted"),
            "latest": StatusSerializer(latest).data if latest else None,
            "required_documents": [{"kind": k, "label": label} for k, label in VerificationDocument.Kind.choices],
            "disclaimer": DISCLAIMER,
            "privacy": "We keep only the last 4 characters of your ID number. Documents are stored privately, seen only by "
                       "our verification team, and deleted after the review period.",
        })

    def post(self, request):
        landlord = self._landlord(request)
        serializer = SubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        files = {kind: request.FILES[kind] for kind in VerificationDocument.Kind.values if kind in request.FILES}
        verification = services.submit(landlord, user=request.user, data=serializer.validated_data, files=files)
        return Response(StatusSerializer(verification).data, status=201)
