from rest_framework import serializers

from apps.properties.models import Unit
from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    REASONS = (
        ("fraudulent_listing", "Fraudulent or fake listing"),
        ("misleading_information", "Misleading price, photos or details"),
        ("inappropriate_content", "Inappropriate content"),
        ("suspicious_payment_request", "Asked to pay outside the platform or in advance"),
        ("harassment", "Harassment or abuse"),
        ("other", "Something else"),
    )
    reason = serializers.ChoiceField(choices=REASONS)
    listing_id = serializers.PrimaryKeyRelatedField(source="listing", queryset=Unit.objects.all(), required=True, write_only=True)
    detail = serializers.CharField(max_length=2000, required=False, allow_blank=True)

    class Meta:
        model = Report
        fields = ("id", "reason", "listing_id", "detail", "created_at")
        read_only_fields = ("id", "created_at")
