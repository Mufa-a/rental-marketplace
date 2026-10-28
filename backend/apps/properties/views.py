import hashlib
import json
import os
from datetime import timedelta
from uuid import uuid4

import boto3
from botocore.config import Config
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, Min, ProtectedError, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import LandlordProfile, TenantProfile, User
from apps.core.models import AuditLog
from apps.core.permissions import is_platform_admin

from .models import Amenity, Property, PropertyMedia, SavedUnit, Unit, UnitDailyStat
from .permissions import IsLandlordOrAdmin, can_manage
from .search import ORDERINGS, SearchFilters, apply_filters, apply_ordering, public_units
from .serializers import (
    AmenitySerializer, PresignUploadSerializer, PropertyMediaSerializer, PropertySerializer, PublicUnitSerializer,
    SavedUnitSerializer, UnitSerializer,
)


def _profile_for(request):
    if request.user.role == User.Role.LANDLORD:
        return LandlordProfile.objects.get_or_create(user=request.user)[0]
    landlord_user_id = request.data.get("landlord_user_id")
    if not landlord_user_id:
        raise ValidationError({"landlord_user_id": "Required when an admin creates a property."})
    return get_object_or_404(LandlordProfile, user_id=landlord_user_id)


def _audit(request, action, obj, **metadata):
    AuditLog.objects.create(actor=request.user, action=action, object_type=obj._meta.label, object_id=str(obj.pk), metadata=metadata)


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
    if not is_platform_admin(request.user):
        properties = properties.filter(landlord__user=request.user)
    return get_object_or_404(properties, pk=property_id)


def _owned_unit(request, unit_id):
    units = Unit.objects.select_related("property__landlord__user")
    if not is_platform_admin(request.user):
        units = units.filter(property__landlord__user=request.user)
    return get_object_or_404(units, pk=unit_id)


def _public_queryset():
    return public_units().select_related("property__landlord").prefetch_related("amenities", "media")


def find_possible_duplicate(unit):
    """Another landlord's listing that looks like the same home: same place, rent, size, and title or address."""
    prop = unit.property
    return (Unit.objects.exclude(pk=unit.pk).exclude(property__landlord=prop.landlord)
            .filter(property__city__iexact=prop.city, property__area__iexact=prop.area, monthly_rent=unit.monthly_rent,
                    bedrooms=unit.bedrooms, unit_type=unit.unit_type)
            .filter(Q(title__iexact=unit.title) | Q(property__address_line__iexact=prop.address_line))
            .order_by("created_at").first())


def _hold_for_review(unit, note, duplicate=None):
    unit.moderation_status = Unit.ModerationStatus.PENDING_REVIEW
    unit.moderation_note = note[:500]
    fields = ["moderation_status", "moderation_note", "updated_at"]
    if duplicate is not None:
        unit.possible_duplicate_of = duplicate
        fields.append("possible_duplicate_of")
    unit.save(update_fields=fields)


class AmenityListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(AmenitySerializer(Amenity.objects.all(), many=True).data)


class LocationSuggestView(APIView):
    """GET /properties/locations/?q=kil — counties, towns and estates that currently have homes, with counts."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_search"

    def get(self, request):
        q = request.query_params.get("q", "").strip()[:60]
        version = cache.get_or_set("public-listings:version", 1, timeout=None)
        key = f"locations:{version}:{hashlib.sha256(q.lower().encode()).hexdigest()}"
        if (cached := cache.get(key)) is not None:
            return Response(cached)
        units = public_units()
        if q:
            units = units.filter(Q(property__area__icontains=q) | Q(property__city__icontains=q) | Q(property__county__icontains=q))
        rows = (units.values("property__county", "property__city", "property__area")
                .annotate(listings=Count("id"), lowest_rent=Min("monthly_rent")).order_by("-listings", "property__area")[:20])
        data = [{"county": r["property__county"], "town": r["property__city"], "estate": r["property__area"],
                 "listings": r["listings"], "lowest_rent": r["lowest_rent"]} for r in rows]
        cache.set(key, data, timeout=300)
        return Response(data)


class SavedUnitListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def _tenant(self, request):
        if request.user.role != User.Role.TENANT:
            raise PermissionDenied("Only tenants can save rental homes.")
        return TenantProfile.objects.get_or_create(user=request.user)[0]

    def get(self, request):
        tenant = self._tenant(request)
        saved = SavedUnit.objects.filter(tenant=tenant).select_related("unit__property__landlord").prefetch_related("unit__amenities", "unit__media")
        available = set(public_units().filter(saved_by__tenant=tenant).values_list("pk", flat=True))
        return Response(SavedUnitSerializer(saved, many=True, context={"available_ids": available}).data)

    def post(self, request):
        tenant = self._tenant(request)
        serializer = SavedUnitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unit = serializer.validated_data["unit"]
        if not public_units().filter(pk=unit.pk).exists():
            raise ValidationError("This home is no longer available to save.")
        saved, created = SavedUnit.objects.get_or_create(tenant=tenant, unit=unit)
        if created:
            _audit(request, "unit.saved", saved)
        return Response(SavedUnitSerializer(saved, context={"available_ids": {unit.pk}}).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class SavedUnitDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, unit_id):
        if request.user.role != User.Role.TENANT:
            raise PermissionDenied("Only tenants can manage saved homes.")
        saved = get_object_or_404(SavedUnit, tenant__user=request.user, unit_id=unit_id)
        _audit(request, "unit.unsaved", saved)
        saved.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SearchPagination(CursorPagination):
    page_size = 20


class PublicUnitSearchView(APIView):
    """Public listing search. Filters are documented in apps/properties/search.py."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_search"

    def get(self, request):
        filters = SearchFilters(data=request.query_params)
        filters.is_valid(raise_exception=True)
        params = filters.validated_data
        query_key = hashlib.sha256(json.dumps(sorted(request.query_params.items()), separators=(",", ":")).encode()).hexdigest()
        version = cache.get_or_set("public-listings:version", 1, timeout=None)
        cache_key = f"public-listings:{version}:{query_key}"
        if (cached := cache.get(cache_key)) is not None:
            return Response(cached)
        units = apply_filters(_public_queryset(), params)
        units, ordering = apply_ordering(units, params)
        total = units.order_by().values("pk").distinct().count()
        paginator = SearchPagination()
        paginator.ordering = ordering
        page = paginator.paginate_queryset(units, request, view=self)
        response = paginator.get_paginated_response(PublicUnitSerializer(page, many=True).data)
        response.data["count"] = total
        response.data["ordering"] = params["ordering"]
        response.data["orderings"] = [{"value": key, "label": label} for key, label in ORDERINGS.items()]
        cache.set(cache_key, response.data, timeout=60)
        return response


def record_listing_view(request, unit):
    """Count one view per visitor per listing per 6 hours. Only a salted, expiring hash is kept, in cache."""
    agent = request.META.get("HTTP_USER_AGENT", "")
    if not agent or any(word in agent.lower() for word in ("bot", "crawler", "spider", "preview")):
        return
    if request.user.is_authenticated and (request.user.pk == unit.property.landlord.user_id or is_platform_admin(request.user)):
        return
    ident = ScopedRateThrottle().get_ident(request)
    visitor = hashlib.sha256(f"{settings.SECRET_KEY}:{ident}:{agent}:{unit.pk}".encode()).hexdigest()[:32]
    if not cache.add(f"listing-view:{visitor}", 1, timeout=6 * 3600):
        return
    stat, _ = UnitDailyStat.objects.get_or_create(unit=unit, date=timezone.localdate())
    UnitDailyStat.objects.filter(pk=stat.pk).update(views=F("views") + 1)


class PublicUnitDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        return Response(PublicUnitSerializer(get_object_or_404(_public_queryset(), slug=slug)).data)


class ListingViewBeaconView(APIView):
    """POST /properties/listings/<slug>/view/ — the browser reports a real page view.

    Counting happens here rather than on the detail GET, which the Next.js server
    calls while rendering (and caches), so server renders and crawlers do not inflate views.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_search"

    def post(self, request, slug):
        unit = public_units().select_related("property__landlord").filter(slug=slug).first()
        if unit:
            record_listing_view(request, unit)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyPropertyListCreateView(APIView):
    permission_classes = [IsLandlordOrAdmin]

    def get(self, request):
        properties = Property.objects.select_related("landlord__user")
        if not is_platform_admin(request.user):
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
        before = (property.address_line, property.area, property.city, property.county, property.location)
        property = serializer.save()
        moved = before != (property.address_line, property.area, property.city, property.county, property.location)
        if moved and property.verification_status == Property.VerificationStatus.VERIFIED and not is_platform_admin(request.user):
            # A verification describes a specific place; moving it means re-checking it (no new fee).
            property.verification_status = Property.VerificationStatus.NEEDS_REVIEW
            property.save(update_fields=("verification_status", "updated_at"))
            _audit(request, "property.verification_needs_review", property, reason="location_changed")
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

    @transaction.atomic
    def post(self, request, property_id):
        property = _owned_property(request, property_id)
        serializer = UnitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        initial = Unit.ModerationStatus.PENDING_REVIEW if settings.LISTINGS_REQUIRE_APPROVAL else Unit.ModerationStatus.APPROVED
        unit = serializer.save(property=property, availability_confirmed_at=timezone.now(), moderation_status=initial)
        duplicate = find_possible_duplicate(unit)
        if duplicate:
            _hold_for_review(unit, "This looks like another landlord's listing. Our team will check it before it goes live.", duplicate)
        _audit(request, "unit.created", unit, moderation_status=unit.moderation_status, possible_duplicate=bool(duplicate))
        transaction.on_commit(_invalidate_public_listing_cache)
        return Response(UnitSerializer(unit).data, status=status.HTTP_201_CREATED)


class UnitDetailView(APIView):
    permission_classes = [IsLandlordOrAdmin]

    def get(self, request, unit_id):
        return Response(UnitSerializer(_owned_unit(request, unit_id)).data)

    def patch(self, request, unit_id):
        unit = _owned_unit(request, unit_id)
        serializer = UnitSerializer(unit, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        admin = is_platform_admin(request.user)
        if unit.moderation_hold and not admin and serializer.validated_data.get("is_published"):
            return Response({"error": {"code": "under_review", "message": "This listing is under review and cannot be republished yet. Please contact support."}}, status=status.HTTP_403_FORBIDDEN)
        unit = serializer.save()
        if not admin and unit.moderation_status in (Unit.ModerationStatus.CHANGES_REQUESTED, Unit.ModerationStatus.REJECTED):
            # Editing after moderator feedback resubmits the listing for review.
            unit.moderation_status = Unit.ModerationStatus.PENDING_REVIEW
            unit.save(update_fields=("moderation_status", "updated_at"))
        _audit(request, "unit.updated", unit, fields=sorted(serializer.validated_data))
        _invalidate_public_listing_cache()
        return Response(UnitSerializer(unit).data)

    def delete(self, request, unit_id):
        unit = _owned_unit(request, unit_id)
        return _delete_or_conflict(request, unit, "unit.deleted", "home", "Mark it as not available or unpublish it instead.")


class UnitAvailabilityView(APIView):
    """POST {"available": bool} — the landlord reconfirms availability, or marks the home occupied."""

    permission_classes = [IsLandlordOrAdmin]

    class AvailabilitySerializer(serializers.Serializer):
        available = serializers.BooleanField()

    @transaction.atomic
    def post(self, request, unit_id):
        unit = _owned_unit(request, unit_id)
        serializer = self.AvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        was_available = unit.available
        unit.available = serializer.validated_data["available"]
        unit.availability_confirmed_at = timezone.now()
        unit.save(update_fields=("available", "availability_confirmed_at", "updated_at"))
        _audit(request, "unit.availability_confirmed", unit, available=unit.available)
        if was_available and not unit.available:
            on_unit_unavailable(unit, request.user)
        transaction.on_commit(_invalidate_public_listing_cache)
        return Response(UnitSerializer(unit).data)


def on_unit_unavailable(unit, actor):
    from apps.notifications.services import notify
    from apps.referrals.services import on_unit_marked_occupied
    from apps.viewings.models import ViewingRequest
    from apps.viewings.services import cancel_request

    # Pending requests can no longer lead anywhere: close them and return the tenants' credits.
    for request_id in ViewingRequest.objects.filter(unit=unit, status=ViewingRequest.Status.PENDING).values_list("pk", flat=True):
        cancel_request(request_id, unit.property.landlord.user, reason="The home is no longer available.")
    for saved in SavedUnit.objects.filter(unit=unit).select_related("tenant__user"):
        notify(recipient=saved.tenant.user, event="listing.unavailable", sms=False,
               dedupe_key=f"saved:{saved.pk}:unavailable:{timezone.localdate():%Y%m%d}", title="A saved home is no longer available",
               message=f"{unit.title} in {unit.property.area} is no longer available.", link="/saved")
    on_unit_marked_occupied(unit, actor)


class LandlordStatsView(APIView):
    """GET /properties/mine/stats/ — listing performance for the signed-in landlord's own units."""

    permission_classes = [IsLandlordOrAdmin]

    def get(self, request):
        from apps.viewings.models import Viewing, ViewingRequest

        units = Unit.objects.filter(property__landlord__user=request.user)
        today = timezone.localdate()
        views = {row["unit_id"]: row for row in UnitDailyStat.objects.filter(unit__in=units, date__gte=today - timedelta(days=29))
                 .values("unit_id").annotate(views_30d=Sum("views"), views_7d=Sum("views", filter=Q(date__gte=today - timedelta(days=6))))}
        requests = {row["unit_id"]: row for row in ViewingRequest.objects.filter(unit__in=units).values("unit_id").annotate(
            total=Count("id"),
            pending=Count("id", filter=Q(status=ViewingRequest.Status.PENDING)),
            approved=Count("id", filter=Q(status=ViewingRequest.Status.APPROVED)),
            completed=Count("id", filter=Q(viewing__completed_at__isnull=False)),
            rented=Count("id", filter=Q(viewing__status=Viewing.Status.RENTED)),
        )}
        saves = dict(SavedUnit.objects.filter(unit__in=units).values("unit_id").annotate(n=Count("id")).values_list("unit_id", "n"))
        visible = set(public_units().filter(pk__in=units).values_list("pk", flat=True))
        rows = []
        for unit in units.select_related("property").order_by("property__name", "unit_number"):
            v, r = views.get(unit.pk, {}), requests.get(unit.pk, {})
            rows.append({
                "unit_id": unit.pk, "title": unit.title, "property": unit.property.name,
                "visible_in_search": unit.pk in visible, "moderation_status": unit.moderation_status,
                "views_7d": v.get("views_7d") or 0, "views_30d": v.get("views_30d") or 0, "saves": saves.get(unit.pk, 0),
                "requests": r.get("total", 0), "pending": r.get("pending", 0), "approved": r.get("approved", 0),
                "completed": r.get("completed", 0), "rented": r.get("rented", 0),
            })
        totals = {key: sum(row[key] for row in rows) for key in ("views_7d", "views_30d", "saves", "requests", "pending", "approved", "completed", "rented")}
        totals["request_rate"] = round(totals["requests"] / totals["views_30d"], 3) if totals["views_30d"] else None
        return Response({"totals": totals, "units": rows})


def _r2_client(**extra):
    return boto3.client("s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL, aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY, **extra)


def _r2_configured():
    return all((settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, settings.AWS_STORAGE_BUCKET_NAME,
                settings.AWS_S3_ENDPOINT_URL, settings.R2_PUBLIC_BASE_URL))


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
        if not _r2_configured():
            raise ValidationError("Photo storage is not configured.")
        if unit.media.count() >= 20:
            raise ValidationError("A listing can have up to 20 photos.")
        try:
            uploaded_object = _r2_client().head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=asset_key)
        except Exception:
            raise ValidationError({"asset_key": "The uploaded photo could not be verified. Upload it again."})
        if uploaded_object.get("ContentLength", 10 * 1024 * 1024 + 1) > 10 * 1024 * 1024 or uploaded_object.get("ContentType") not in ("image/jpeg", "image/png", "image/webp"):
            raise ValidationError({"asset_key": "The uploaded object is not an accepted image under 10 MB."})
        content_hash = str(uploaded_object.get("ETag", "")).strip('"')[:64]
        media = serializer.save(unit=unit, content_hash=content_hash)
        reused = bool(content_hash) and PropertyMedia.objects.filter(content_hash=content_hash).exclude(unit__property__landlord=unit.property.landlord).exists()
        if reused and unit.moderation_status == Unit.ModerationStatus.APPROVED:
            _hold_for_review(unit, "A photo on this listing also appears on another landlord's listing. Our team will check it.")
        _audit(request, "property_media.created", media, reused_photo=reused)
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
    """Return a short-lived R2 presigned PUT; the image never passes through Django."""
    permission_classes = [IsLandlordOrAdmin]

    def post(self, request, unit_id):
        unit = _owned_unit(request, unit_id)
        serializer = PresignUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not _r2_configured():
            raise ValidationError("Photo storage is not configured.")
        extension = os.path.splitext(serializer.validated_data["filename"])[1].lower()
        asset_key = f"properties/{unit.id}/{uuid4().hex}{extension}"
        content_type = serializer.validated_data["content_type"]
        upload_url = _r2_client(region_name="auto", config=Config(signature_version="s3v4")).generate_presigned_url(
            "put_object",
            Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": asset_key, "ContentType": content_type},
            ExpiresIn=300,
        )
        return Response({
            "asset_key": asset_key,
            "upload": {"url": upload_url, "method": "PUT", "headers": {"Content-Type": content_type}},
            "expires_in_seconds": 300,
        })
