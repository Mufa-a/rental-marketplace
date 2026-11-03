from rest_framework import serializers

from apps.properties.models import Unit

from .models import Outcome, Viewing, ViewingRequest


class ViewingSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Viewing
        fields = ("id", "scheduled_at", "status", "meeting_note", "completed_at", "reschedule_count")


def _display_name(user, fallback):
    name = " ".join(part for part in (user.first_name, user.last_name) if part).strip()
    return name or fallback


class RequestSerializer(serializers.ModelSerializer):
    unit = serializers.PrimaryKeyRelatedField(queryset=Unit.objects.select_related("property__landlord__user"))
    viewing = serializers.SerializerMethodField()
    unit_title = serializers.CharField(source="unit.title", read_only=True)
    unit_slug = serializers.CharField(source="unit.slug", read_only=True)
    unit_path = serializers.SerializerMethodField()
    property_name = serializers.CharField(source="unit.property.name", read_only=True)
    area = serializers.CharField(source="unit.property.area", read_only=True)
    city = serializers.CharField(source="unit.property.city", read_only=True)
    monthly_rent = serializers.IntegerField(source="unit.monthly_rent", read_only=True)
    unit_available = serializers.BooleanField(source="unit.available", read_only=True)
    my_role = serializers.SerializerMethodField()
    my_outcome = serializers.SerializerMethodField()
    contact = serializers.SerializerMethodField()

    class Meta:
        model = ViewingRequest
        fields = ("id", "unit", "unit_title", "unit_slug", "unit_path", "property_name", "area", "city", "monthly_rent", "unit_available",
                  "preferred_times", "note", "status", "landlord_note", "responded_at", "cancelled_by", "cancel_reason",
                  "viewing", "my_role", "my_outcome", "contact", "created_at", "updated_at")
        read_only_fields = ("id", "status", "landlord_note", "responded_at", "cancelled_by", "cancel_reason", "viewing", "created_at", "updated_at")

    def validate_preferred_times(self, value):
        if not isinstance(value, list) or len(value) > 5 or any(not isinstance(item, str) or len(item) > 60 for item in value):
            raise serializers.ValidationError("Give up to five short preferred times.")
        return value

    def get_unit_path(self, obj):
        from apps.properties.search import listing_path
        return listing_path(obj.unit)

    def _user(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def get_viewing(self, obj):
        try:
            return ViewingSummarySerializer(obj.viewing).data
        except Viewing.DoesNotExist:
            return None

    def get_my_role(self, obj):
        user = self._user()
        if not user:
            return None
        if obj.tenant.user_id == user.id:
            return "tenant"
        if obj.unit.property.landlord.user_id == user.id:
            return "landlord"
        return "admin"

    def get_my_outcome(self, obj):
        user = self._user()
        viewing = getattr(obj, "viewing", None)  # reverse one-to-one: missing raises an AttributeError subclass
        if not user or viewing is None:
            return None
        outcome = next((o for o in viewing.outcomes.all() if o.reporter_id == user.id), None)
        return outcome.choice if outcome else None

    def get_contact(self, obj):
        """Released only for an approved viewing that is not cancelled, and only to its two parties."""
        user = self._user()
        try:
            viewing = obj.viewing
        except Viewing.DoesNotExist:
            return None
        if not user or obj.status != ViewingRequest.Status.APPROVED or viewing.status == Viewing.Status.CANCELLED:
            return None
        prop = obj.unit.property
        if obj.tenant.user_id == user.id:
            landlord = prop.landlord.user
            return {
                "address": prop.address_line, "area": prop.area, "city": prop.city, "county": prop.county,
                "latitude": prop.location.latitude if prop.location else None,
                "longitude": prop.location.longitude if prop.location else None,
                "name": _display_name(landlord, "Landlord"), "phone": landlord.phone_number,
                "meeting_note": viewing.meeting_note,
            }
        if prop.landlord.user_id == user.id:
            tenant = obj.tenant.user
            return {"name": _display_name(tenant, "Tenant"), "phone": tenant.phone_number}
        return None


class ApprovalSerializer(serializers.Serializer):
    scheduled_at = serializers.DateTimeField()
    meeting_note = serializers.CharField(max_length=500, required=False, allow_blank=True)


class RescheduleSerializer(serializers.Serializer):
    scheduled_at = serializers.DateTimeField()
    meeting_note = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ReasonSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class ViewingSerializer(serializers.ModelSerializer):
    request = serializers.SerializerMethodField()

    class Meta:
        model = Viewing
        fields = ("id", "request", "scheduled_at", "status", "meeting_note", "completed_at", "reschedule_count", "created_at")
        read_only_fields = fields

    def get_request(self, obj):
        return RequestSerializer(obj.request, context=self.context).data


class OutcomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Outcome
        fields = ("id", "viewing", "choice", "note", "created_at")
        read_only_fields = ("id", "viewing", "created_at")
