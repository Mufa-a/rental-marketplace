import hashlib
import json
import math
import os
from uuid import uuid4
from datetime import timedelta

import boto3
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.models import ProtectedError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import LandlordProfile, User
from apps.core.models import AuditLog

from .models import Amenity, Property, PropertyMedia, SavedUnit, Unit
from .permissions import IsLandlordOrAdmin, can_manage
from .serializers import AmenitySerializer, PresignUploadSerializer, PropertyMediaSerializer, PropertySerializer, SavedUnitSerializer, UnitSerializer


def _profile_for(request):
    if request.user.role == User.Role.LANDLORD:
        return LandlordProfile.objects.get_or_create(user=request.user)[0]
    landlord_user_id = request.data.get("landlord_user_id")
    if not landlord_user_id:
        raise ValidationError({"landlord_user_id": "Required when an admin creates a property."})
    return get_object_or_404(LandlordProfile, user_id=landlord_user_id)


def _audit(request, action, obj):
    AuditLog.objects.create(actor=request.user, action=action, object_type=obj._meta.label, object_id=str(obj.pk))


def _delete_or_conflict(request, obj, action, what, alternative):
    """Delete obj unless viewing history references it; never a 500, never a silent loss of records."""
    object_pk = obj.pk
    label = obj._meta.label
    try:
        obj.delete()
    except ProtectedError:
        return Response(
            {"error": {"code": "has_history", "message": f"This {what} has viewing or payment history, so it can't be deleted. {alternative}"}},
            status=status.HTTP_409_CONFLICT,
        )
    AuditLog.objects.create(actor=request.user, action=action, object_type=label, object_id=str(object_pk))
    _invalidate_public_listing_cache()
    return Response(status=status.HTTP_204_NO_CONTENT)


def _invalidate_public_listing_cache():
    cache.add("public-listings:version", 1, timeout=None)
    cache.incr("public-listings:version")


def _owned_property(request, property_id):
    properties = Property.objects.select_related("landlord__user")
    if request.user.role != User.Role.ADMIN:
        properties = properties.filter(landlord__user=request.user)
    return get_object_or_404(properties, pk=property_id)


def _owned_unit(request, unit_id):
    units = Unit.objects.select_related("property__landlord__user")
    if request.user.role != User.Role.ADMIN:
        units = units.filter(property__landlord__user=request.user)
    return get_object_or_404(units, pk=unit_id)


class AmenityListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(AmenitySerializer(Amenity.objects.all(), many=True).data)


class SavedUnitListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def _tenant(self, request):
        if request.user.role != User.Role.TENANT:
            raise PermissionDenied("Only tenants can save rental homes.")
        from apps.accounts.models import TenantProfile
        return TenantProfile.objects.get_or_create(user=request.user)[0]

    def get(self, request):
        tenant = self._tenant(request)
        saved = SavedUnit.objects.filter(tenant=tenant).select_related("unit__property").prefetch_related("unit__amenities", "unit__media")
        return Response(SavedUnitSerializer(saved, many=True).data)

    def post(self, request):
        tenant = self._tenant(request)
        serializer = SavedUnitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unit = serializer.validated_data["unit"]
        if not unit.is_published or not unit.available or not unit.property.is_active:
            raise ValidationError("This home is no longer available to save.")
        saved, created = SavedUnit.objects.get_or_create(tenant=tenant, unit=unit)
        if created:
            _audit(request, "unit.saved", saved)
        return Response(SavedUnitSerializer(saved).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class SavedUnitDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, unit_id):
        if request.user.role != User.Role.TENANT:
            raise PermissionDenied("Only tenants can manage saved homes.")
        saved = get_object_or_404(SavedUnit, tenant__user=request.user, unit_id=unit_id)
        _audit(request, "unit.unsaved", saved)
        saved.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicUnitSearchView(APIView):
    """Public, availability-only listing query used by the Phase 4 search UI."""
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_search"

    class FiltersSerializer(serializers.Serializer):
        city = serializers.CharField(max_length=100, required=False)
        area = serializers.CharField(max_length=100, required=False)
        min_rent = serializers.IntegerField(min_value=0, required=False)
        max_rent = serializers.IntegerField(min_value=1, required=False)
        bedrooms = serializers.IntegerField(min_value=0, required=False)
        amenity = serializers.SlugField(max_length=90, required=False)
        unit_type = serializers.ChoiceField(choices=Unit.UnitType.choices, required=False)
        move_in_date = serializers.DateField(required=False)
        latitude = serializers.FloatField(min_value=-90, max_value=90, required=False)
        longitude = serializers.FloatField(min_value=-180, max_value=180, required=False)
        radius_km = serializers.FloatField(min_value=0.1, max_value=100, required=False)
        ordering = serializers.ChoiceField(choices=("-created_at", "monthly_rent", "-monthly_rent", "bedrooms", "distance"), required=False, default="-created_at")

        def validate(self, attrs):
            if attrs.get("min_rent", 0) > attrs.get("max_rent", 2**31 - 1):
                raise serializers.ValidationError("Minimum rent must not exceed maximum rent.")
            if ("latitude" in attrs) != ("longitude" in attrs):
                raise serializers.ValidationError("Latitude and longitude must be provided together.")
            if "radius_km" in attrs and "latitude" not in attrs:
                raise serializers.ValidationError("Radius search requires latitude and longitude.")
            if attrs.get("ordering") == "distance" and "latitude" not in attrs:
                raise serializers.ValidationError("Distance sorting requires your location.")
            return attrs

    def get(self, request):
        filters = self.FiltersSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        params = filters.validated_data
        query_key = hashlib.sha256(json.dumps(sorted(request.query_params.items()), separators=(",", ":")).encode()).hexdigest()
        version = cache.get_or_set("public-listings:version", "1")
        cache_key = f"public-listings:{version}:{query_key}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        units = Unit.objects.filter(
            is_published=True, available=True, property__is_active=True,
            availability_confirmed_at__gte=timezone.now() - timedelta(days=30),
        ).select_related("property").prefetch_related("amenities", "media")
        for field in ("city", "area"):
            if value := params.get(field):
                units = units.filter(**{f"property__{field}__icontains": value.strip()})
        if "min_rent" in params:
            units = units.filter(monthly_rent__gte=params["min_rent"])
        if "max_rent" in params:
            units = units.filter(monthly_rent__lte=params["max_rent"])
        if "bedrooms" in params:
            units = units.filter(bedrooms=params["bedrooms"]) if params["bedrooms"] == 0 else units.filter(bedrooms__gte=params["bedrooms"])
        if "unit_type" in params:
            units = units.filter(unit_type=params["unit_type"])
        if "move_in_date" in params:
            units = units.filter(Q(available_from__isnull=True) | Q(available_from__lte=params["move_in_date"]))
        if "amenity" in params:
            units = units.filter(amenities__slug=params["amenity"])
        if "radius_km" in params:
            longitude, latitude = params["longitude"], params["latitude"]
            if connection.vendor == "postgresql":
                nearby_properties = Property.objects.extra(
                    where=["ST_DWithin(properties_property.location, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)"],
                    params=[longitude, latitude, params["radius_km"] * 1000],
                ).values("id")
                units = units.filter(property_id__in=nearby_properties)
            else:
                from .fields import GeographicPoint
                property_ids = []
                for property_id, point in Property.objects.exclude(location__isnull=True).values_list("id", "location"):
                    if isinstance(point, GeographicPoint):
                        dlat = math.radians(point.latitude - latitude)
                        dlon = math.radians(point.longitude - longitude)
                        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(latitude)) * math.cos(math.radians(point.latitude)) * math.sin(dlon / 2) ** 2
                        if 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)) <= params["radius_km"]:
                            property_ids.append(property_id)
                units = units.filter(property_id__in=property_ids)
        if params.get("ordering") == "distance" and connection.vendor == "postgresql":
            from django.contrib.gis.db.models.functions import Distance
            from django.contrib.gis.geos import Point
            center = Point(params["longitude"], params["latitude"], srid=4326)
            units = units.annotate(distance=Distance("property__location", center)).order_by("distance", "id")
        else:
            ordering = params["ordering"]
            units = units.distinct().order_by("-created_at" if ordering == "distance" else ordering, "id")
        paginator = CursorPagination()
        paginator.page_size = 20
        paginator.ordering = (params["ordering"], "id")
        page = paginator.paginate_queryset(units, request, view=self)
        data = UnitSerializer(page, many=True).data
        for item, unit in zip(data, page):
            item["property"] = {
                "area": unit.property.area, "city": unit.property.city,
                "verification_status": unit.property.verification_status,
            }
            if unit.property.location:
                # Approximate public map pins to protect the exact home entrance location.
                item["property"]["latitude"] = round(unit.property.location.latitude, 3)
                item["property"]["longitude"] = round(unit.property.location.longitude, 3)
        response = paginator.get_paginated_response(data)
        cache.set(cache_key, response.data, timeout=60)
        return response


class PublicUnitDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        unit = get_object_or_404(
            Unit.objects.select_related("property").prefetch_related("amenities", "media"),
            slug=slug, is_published=True, available=True, property__is_active=True,
            availability_confirmed_at__gte=timezone.now() - timedelta(days=30),
        )
        data = UnitSerializer(unit).data
        data["property"] = {
            "name": unit.property.name, "area": unit.property.area, "city": unit.property.city,
            "county": unit.property.county, "country": unit.property.country,
            "verification_status": unit.property.verification_status,
        }
        return Response(data)


class MyPropertyListCreateView(APIView):
    permission_classes = [IsLandlordOrAdmin]

    def get(self, request):
        properties = Property.objects.select_related("landlord__user")
        if request.user.role != User.Role.ADMIN:
            properties = properties.filter(landlord__user=request.user)
        return Response(PropertySerializer(properties, many=True).data)

    def post(self, request):
        serializer = PropertySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        property = serializer.save(landlord=_profile_for(request))
        _audit(request, "property.created", property)
        _invalidate_public_listing_cache()
        return Response(PropertySerializer(property).data, status=status.HTTP_201_CREATED)


class PropertyDetailView(APIView):
    permission_classes = [IsLandlordOrAdmin]

    def get(self, request, property_id):
        return Response(PropertySerializer(_owned_property(request, property_id)).data)

    def patch(self, request, property_id):
        property = _owned_property(request, property_id)
        serializer = PropertySerializer(property, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        property = serializer.save()
        _audit(request, "property.updated", property)
        _invalidate_public_listing_cache()
        return Response(PropertySerializer(property).data)

    def delete(self, request, property_id):
        property = _owned_property(request, property_id)
        return _delete_or_conflict(request, property, "property.deleted", "property", "Set it to inactive instead to hide it from search.")


class UnitListCreateView(APIView):
    permission_classes = [IsLandlordOrAdmin]

    def get(self, request, property_id):
        property = _owned_property(request, property_id)
        return Response(UnitSerializer(property.units.prefetch_related("amenities", "media"), many=True).data)

    def post(self, request, property_id):
        property = _owned_property(request, property_id)
        serializer = UnitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unit = serializer.save(property=property, availability_confirmed_at=timezone.now())
        _audit(request, "unit.created", unit)
        _invalidate_public_listing_cache()
        return Response(UnitSerializer(unit).data, status=status.HTTP_201_CREATED)


class UnitDetailView(APIView):
    permission_classes = [IsLandlordOrAdmin]

    def get(self, request, unit_id):
        return Response(UnitSerializer(_owned_unit(request, unit_id)).data)

    def patch(self, request, unit_id):
        unit = _owned_unit(request, unit_id)
        serializer = UnitSerializer(unit, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        unit = serializer.save()
        _audit(request, "unit.updated", unit)
        _invalidate_public_listing_cache()
        return Response(UnitSerializer(unit).data)

    def delete(self, request, unit_id):
        unit = _owned_unit(request, unit_id)
        return _delete_or_conflict(request, unit, "unit.deleted", "home", "Mark it as not available or unpublish it instead.")


class UnitAvailabilityView(APIView):
    permission_classes = [IsLandlordOrAdmin]

    class AvailabilitySerializer(serializers.Serializer):
        available = serializers.BooleanField()

    def post(self, request, unit_id):
        unit = _owned_unit(request, unit_id)
        serializer = self.AvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unit.available = serializer.validated_data["available"]
        unit.availability_confirmed_at = timezone.now()
        unit.save(update_fields=("available", "availability_confirmed_at", "updated_at"))
        _audit(request, "unit.availability_confirmed", unit)
        _invalidate_public_listing_cache()
        return Response(UnitSerializer(unit).data)


class MediaListCreateView(APIView):
    permission_classes = [IsLandlordOrAdmin]

    def get(self, request, unit_id):
        unit = _owned_unit(request, unit_id)
        return Response(PropertyMediaSerializer(unit.media.all(), many=True).data)

    def post(self, request, unit_id):
        unit = _owned_unit(request, unit_id)
        serializer = PropertyMediaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asset_key = serializer.validated_data["asset_key"]
        if not asset_key.startswith(f"properties/{unit.id}/"):
            raise ValidationError({"asset_key": "This upload key does not belong to the unit."})
        if not all((settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, settings.AWS_STORAGE_BUCKET_NAME, settings.AWS_S3_ENDPOINT_URL, settings.R2_PUBLIC_BASE_URL)):
            raise ValidationError("R2 storage is not configured.")
        client = boto3.client("s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL, aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
        try:
            uploaded_object = client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=asset_key)
        except Exception:
            raise ValidationError({"asset_key": "The uploaded photo could not be verified. Upload it again."})
        if uploaded_object.get("ContentLength", 10 * 1024 * 1024 + 1) > 10 * 1024 * 1024 or uploaded_object.get("ContentType") not in ("image/jpeg", "image/png", "image/webp"):
            raise ValidationError({"asset_key": "The uploaded object is not an accepted image under 10 MB."})
        media = serializer.save(unit=unit)
        _audit(request, "property_media.created", media)
        _invalidate_public_listing_cache()
        return Response(PropertyMediaSerializer(media).data, status=status.HTTP_201_CREATED)


class MediaDetailView(APIView):
    permission_classes = [IsLandlordOrAdmin]

    def delete(self, request, media_id):
        media = get_object_or_404(PropertyMedia.objects.select_related("unit__property__landlord__user"), pk=media_id)
        if not can_manage(request.user, media.unit.property):
            raise PermissionDenied("You cannot manage this media item.")
        _audit(request, "property_media.deleted", media)
        media.delete()
        _invalidate_public_listing_cache()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MediaPresignView(APIView):
    """Return a short-lived R2 form POST; the image never passes through Django."""
    permission_classes = [IsLandlordOrAdmin]

    def post(self, request, unit_id):
        unit = _owned_unit(request, unit_id)
        serializer = PresignUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not all((settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, settings.AWS_STORAGE_BUCKET_NAME, settings.AWS_S3_ENDPOINT_URL, settings.R2_PUBLIC_BASE_URL)):
            raise ValidationError("R2 storage is not configured.")
        extension = os.path.splitext(serializer.validated_data["filename"])[1].lower()
        asset_key = f"properties/{unit.id}/{uuid4().hex}{extension}"
        client = boto3.client("s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL, aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
        upload = client.generate_presigned_post(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=asset_key, Fields={"Content-Type": serializer.validated_data["content_type"]}, Conditions=[{"Content-Type": serializer.validated_data["content_type"]}, ["content-length-range", 1, 10 * 1024 * 1024]], ExpiresIn=300)
        return Response({"asset_key": asset_key, "upload": upload, "expires_in_seconds": 300})
