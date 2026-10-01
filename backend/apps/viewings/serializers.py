from rest_framework import serializers
from .models import Outcome, Viewing, ViewingRequest

class ViewingSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Viewing
        fields = ("id", "scheduled_at", "status", "meeting_note", "completed_at")

class RequestSerializer(serializers.ModelSerializer):
    viewing = serializers.SerializerMethodField()
    unit_title = serializers.CharField(source="unit.title", read_only=True)
    property_name = serializers.CharField(source="unit.property.name", read_only=True)
    area = serializers.CharField(source="unit.property.area", read_only=True)
    monthly_rent = serializers.IntegerField(source="unit.monthly_rent", read_only=True)
    unit_available = serializers.BooleanField(source="unit.available", read_only=True)

    class Meta:
        model = ViewingRequest
        fields = ("id", "unit", "unit_title", "property_name", "area", "monthly_rent", "unit_available", "preferred_times", "note", "status", "landlord_note", "responded_at", "viewing", "created_at", "updated_at")
        read_only_fields = ("id", "status", "landlord_note", "responded_at", "viewing", "created_at", "updated_at")

    def get_viewing(self, obj):
        try:
            return ViewingSummarySerializer(obj.viewing).data
        except Viewing.DoesNotExist:
            return None


class ApprovalSerializer(serializers.Serializer):
    scheduled_at = serializers.DateTimeField()
    meeting_note = serializers.CharField(max_length=500, required=False, allow_blank=True)

class ViewingSerializer(serializers.ModelSerializer):
    request = RequestSerializer(read_only=True)
    class Meta:
        model = Viewing
        fields = ("id", "request", "scheduled_at", "status", "meeting_note", "completed_at", "created_at")
        read_only_fields = ("id", "request", "status", "completed_at", "created_at")

class OutcomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Outcome
        fields = ("id", "viewing", "choice", "note", "created_at")
        read_only_fields = ("id", "viewing", "created_at")
