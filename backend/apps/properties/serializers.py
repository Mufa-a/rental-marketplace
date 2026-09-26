import os

from django.conf import settings
from rest_framework import serializers

from .models import Amenity, Property, PropertyMedia, SavedUnit, Unit
from .fields import GeographicPoint


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
        fields = ("id", "property_id", "unit_number", "slug", "title", "description", "unit_type", "monthly_rent", "security_deposit", "bedrooms", "bathrooms", "floor_area_sqm", "furnishing", "available", "available_from", "is_published", "amenities", "amenity_details", "media", "distance_km", "created_at", "updated_at")
        read_only_fields = ("id", "property_id", "slug", "media", "created_at", "updated_at")

    def get_distance_km(self, obj):
        distance = getattr(obj, "distance", None)
        return round(distance.km, 1) if distance is not None and hasattr(distance, "km") else None


class SavedUnitSerializer(serializers.ModelSerializer):
    unit_id = serializers.PrimaryKeyRelatedField(source="unit", queryset=Unit.objects.all(), write_only=True)
    unit = UnitSerializer(read_only=True)

    class Meta:
        model = SavedUnit
        fields = ("id", "unit_id", "unit", "created_at")
        read_only_fields = ("id", "unit", "created_at")

    def to_representation(self, instance):
        result = super().to_representation(instance)
        property = instance.unit.property
        result["unit"]["property"] = {
            "name": property.name, "area": property.area, "city": property.city,
            "county": property.county, "country": property.country,
        }
        return result


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
