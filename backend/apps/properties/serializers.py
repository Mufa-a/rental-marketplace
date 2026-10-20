import os

from django.conf import settings
from rest_framework import serializers

from .models import Amenity, Property, PropertyMedia, SavedUnit, Unit
from .fields import GeographicPoint
from .media import ALLOWED_TYPES, is_video_type, max_bytes_for


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
    kind = serializers.SerializerMethodField()

    class Meta:
        model = PropertyMedia
        fields = ("id", "asset_key", "url", "kind", "media_type", "alt_text", "sort_order", "created_at")
        read_only_fields = ("id", "url", "kind", "created_at")

    def get_url(self, obj):
        return f"{settings.R2_PUBLIC_BASE_URL}/{obj.asset_key}" if settings.R2_PUBLIC_BASE_URL else ""

    def get_kind(self, obj):
        return "video" if obj.is_video else "image"


class UnitSerializer(serializers.ModelSerializer):
    property_id = serializers.IntegerField(source="property.id", read_only=True)
    amenities = serializers.PrimaryKeyRelatedField(queryset=Amenity.objects.all(), many=True, required=False)
    amenity_details = AmenitySerializer(source="amenities", many=True, read_only=True)
    # `media` is photos only and `video` is the home's single video, so a video can never end up
    # where the site expects an image (cards, thumbnails, the gallery). Filtering in Python keeps
    # the prefetch the list views already do.
    media = serializers.SerializerMethodField()
    video = serializers.SerializerMethodField()
    available = serializers.BooleanField(read_only=True)
    distance_km = serializers.SerializerMethodField()

    class Meta:
        model = Unit
        fields = ("id", "property_id", "unit_number", "slug", "title", "description", "unit_type", "monthly_rent", "security_deposit", "bedrooms", "bathrooms", "floor_area_sqm", "furnishing", "available", "available_from", "is_published", "moderation_hold", "amenities", "amenity_details", "media", "video", "distance_km", "created_at", "updated_at")
        read_only_fields = ("id", "property_id", "slug", "moderation_hold", "media", "created_at", "updated_at")

    def get_media(self, obj):
        return PropertyMediaSerializer([item for item in obj.media.all() if not item.is_video], many=True).data

    def get_video(self, obj):
        video = next((item for item in obj.media.all() if item.is_video), None)
        return PropertyMediaSerializer(video).data if video else None

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
    content_type = serializers.ChoiceField(choices=tuple(ALLOWED_TYPES))
    # Optional: lets an oversize file be refused before it is uploaded at all.
    size = serializers.IntegerField(min_value=1, required=False)

    def validate_filename(self, value):
        if "/" in value or "\\" in value or "." not in value:
            raise serializers.ValidationError("Provide a photo or video filename, not a path.")
        return value

    def validate(self, attrs):
        extension = os.path.splitext(attrs["filename"])[1].lower()
        if extension not in ALLOWED_TYPES[attrs["content_type"]]:
            raise serializers.ValidationError({"filename": "The filename extension must match the file type."})
        size = attrs.get("size")
        limit = max_bytes_for(attrs["content_type"])
        if size is not None and size > limit:
            kind = "video" if is_video_type(attrs["content_type"]) else "photo"
            raise serializers.ValidationError({"size": f"That {kind} is larger than the {limit // (1024 * 1024)} MB limit."})
        return attrs
