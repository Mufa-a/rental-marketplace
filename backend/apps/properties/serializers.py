import os

from django.conf import settings
from rest_framework import serializers

from .models import Amenity, Property, PropertyMedia, SavedUnit, Unit
from .fields import GeographicPoint

MIN_RENT = 500
MAX_RENT = 10_000_000


class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ("id", "name", "slug", "icon")


class PropertySerializer(serializers.ModelSerializer):
    landlord_id = serializers.IntegerField(source="landlord.user_id", read_only=True)
    latitude = serializers.FloatField(write_only=True, required=False, min_value=-90, max_value=90)
    longitude = serializers.FloatField(write_only=True, required=False, min_value=-180, max_value=180)

    class Meta:
        model = Property
        fields = ("id", "landlord_id", "name", "description", "address_line", "area", "city", "county", "country", "latitude", "longitude", "verification_status", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "landlord_id", "verification_status", "created_at", "updated_at")

    def validate(self, attrs):
        current = getattr(self.instance, "location", None)
        latitude = attrs.get("latitude", current.latitude if current else None)
        longitude = attrs.get("longitude", current.longitude if current else None)
        if (latitude is None) != (longitude is None):
            raise serializers.ValidationError("latitude and longitude must be provided together.")
        attrs["latitude"], attrs["longitude"] = latitude, longitude
        return attrs

    def create(self, validated_data):
        latitude = validated_data.pop("latitude", None)
        longitude = validated_data.pop("longitude", None)
        if latitude is not None:
            validated_data["location"] = GeographicPoint(longitude, latitude)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        latitude = validated_data.pop("latitude", None)
        longitude = validated_data.pop("longitude", None)
        if latitude is not None:
            validated_data["location"] = GeographicPoint(longitude, latitude)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["latitude"] = instance.location.latitude if instance.location else None
        data["longitude"] = instance.location.longitude if instance.location else None
        return data


class PropertyMediaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = PropertyMedia
        fields = ("id", "asset_key", "url", "media_type", "alt_text", "sort_order", "created_at")
        read_only_fields = ("id", "url", "created_at")

    def get_url(self, obj):
        return f"{settings.R2_PUBLIC_BASE_URL}/{obj.asset_key}" if settings.R2_PUBLIC_BASE_URL else ""


class UnitSerializer(serializers.ModelSerializer):
    property_id = serializers.IntegerField(source="property.id", read_only=True)
    amenities = serializers.PrimaryKeyRelatedField(queryset=Amenity.objects.all(), many=True, required=False)
    amenity_details = AmenitySerializer(source="amenities", many=True, read_only=True)
    media = PropertyMediaSerializer(many=True, read_only=True)
    available = serializers.BooleanField(read_only=True)
    distance_km = serializers.SerializerMethodField()

    class Meta:
        model = Unit
        fields = ("id", "property_id", "unit_number", "slug", "title", "description", "unit_type", "monthly_rent", "security_deposit", "bedrooms", "bathrooms", "floor_area_sqm", "furnishing", "available", "availability_confirmed_at", "available_from", "is_published", "moderation_hold", "moderation_status", "moderation_note", "amenities", "amenity_details", "media", "distance_km", "created_at", "updated_at")
        read_only_fields = ("id", "property_id", "slug", "availability_confirmed_at", "moderation_hold", "moderation_status", "moderation_note", "media", "created_at", "updated_at")
        extra_kwargs = {"title": {"min_length": 5}, "description": {"max_length": 5000}}

    def get_distance_km(self, obj):
        metres = getattr(obj, "distance_m", None)
        return round(metres / 1000, 1) if metres is not None else None

    def validate_monthly_rent(self, value):
        if not MIN_RENT <= value <= MAX_RENT:
            raise serializers.ValidationError(f"Enter the real monthly rent (between {MIN_RENT:,} and {MAX_RENT:,}).")
        return value

    def validate(self, attrs):
        rent = attrs.get("monthly_rent", getattr(self.instance, "monthly_rent", None))
        deposit = attrs.get("security_deposit", getattr(self.instance, "security_deposit", 0))
        if rent and deposit and deposit > rent * 12:
            raise serializers.ValidationError({"security_deposit": "The deposit looks wrong: it is more than a year's rent."})
        return attrs


class PublicUnitSerializer(serializers.ModelSerializer):
    """What anyone on the internet may see about a listing. No unit number, address or owner identity."""

    amenity_details = AmenitySerializer(source="amenities", many=True, read_only=True)
    media = PropertyMediaSerializer(many=True, read_only=True)
    distance_km = serializers.SerializerMethodField()
    property = serializers.SerializerMethodField()
    path = serializers.SerializerMethodField()

    class Meta:
        model = Unit
        fields = ("id", "slug", "path", "title", "description", "unit_type", "monthly_rent", "security_deposit", "bedrooms",
                  "bathrooms", "floor_area_sqm", "furnishing", "available", "available_from", "availability_confirmed_at",
                  "amenity_details", "media", "distance_km", "property", "created_at", "updated_at")

    def get_distance_km(self, obj):
        metres = getattr(obj, "distance_m", None)
        return round(metres / 1000, 1) if metres is not None else None

    def get_path(self, obj):
        from .search import listing_path
        return listing_path(obj)

    def get_property(self, obj):
        prop = obj.property
        data = {
            "name": prop.name, "area": prop.area, "city": prop.city, "county": prop.county, "country": prop.country,
            "verification_status": prop.verification_status,
            "landlord_verified": prop.landlord.verification_tier in ("standard", "trusted"),
        }
        if prop.location:
            # Approximate (~100 m) so the public map never pinpoints the entrance.
            data["latitude"] = round(prop.location.latitude, 3)
            data["longitude"] = round(prop.location.longitude, 3)
        return data


class SavedUnitSerializer(serializers.ModelSerializer):
    unit_id = serializers.PrimaryKeyRelatedField(source="unit", queryset=Unit.objects.all(), write_only=True)
    unit = PublicUnitSerializer(read_only=True)
    still_available = serializers.SerializerMethodField()

    class Meta:
        model = SavedUnit
        fields = ("id", "unit_id", "unit", "still_available", "created_at")
        read_only_fields = ("id", "unit", "created_at")

    def get_still_available(self, obj):
        available = self.context.get("available_ids")
        if available is None:
            from .search import public_units
            return public_units().filter(pk=obj.unit_id).exists()
        return obj.unit_id in available


class PresignUploadSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=200)
    content_type = serializers.ChoiceField(choices=("image/jpeg", "image/png", "image/webp"))

    def validate_filename(self, value):
        if "/" in value or "\\" in value or "." not in value:
            raise serializers.ValidationError("Provide an image filename, not a path.")
        return value

    def validate(self, attrs):
        allowed_extensions = {
            "image/jpeg": {".jpg", ".jpeg"},
            "image/png": {".png"},
            "image/webp": {".webp"},
        }
        extension = os.path.splitext(attrs["filename"])[1].lower()
        if extension not in allowed_extensions[attrs["content_type"]]:
            raise serializers.ValidationError({"filename": "The filename extension must match the image type."})
        return attrs
