"""Public listing search: one definition of "visible to the public", plus filters and sorting.

Every filter runs in the database. Location text uses case-insensitive matching
backed by trigram indexes on PostgreSQL; radius search and distance sorting use
PostGIS. SQLite (tests) gets an equivalent pure-Python fallback for geography.
"""
import math
from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.db.models import Case, F, FloatField, Func, IntegerField, Q, Value, When
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers

from .fields import GeographicPoint
from .models import Property, Unit

ORDERINGS = {
    "relevance": "Best match",
    "-created_at": "Newest",
    "monthly_rent": "Rent: low to high",
    "-monthly_rent": "Rent: high to low",
    "bedrooms": "Fewest bedrooms",
    "-bedrooms": "Most bedrooms",
    "distance": "Nearest",
}


def public_units():
    """Listings anyone may see: published, available, approved, not on hold, recently reconfirmed."""
    cutoff = timezone.now() - timedelta(days=settings.AVAILABILITY_CONFIRMATION_DAYS)
    return Unit.objects.filter(
        is_published=True, available=True, moderation_hold=False,
        moderation_status=Unit.ModerationStatus.APPROVED,
        property__is_active=True, property__landlord__user__is_active=True,
        availability_confirmed_at__gte=cutoff,
    )


def listing_path(unit):
    """Canonical frontend path. Built server-side so cards, sitemap and canonical tags always agree."""
    prop = unit.property
    return f"/listings/{slugify(prop.city) or 'kenya'}/{slugify(prop.area) or 'area'}/{unit.slug}"


def _csv(value, limit=10):
    return [part.strip() for part in value.split(",") if part.strip()][:limit]


class SearchFilters(serializers.Serializer):
    q = serializers.CharField(max_length=100, required=False, allow_blank=True)
    county = serializers.CharField(max_length=100, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    town = serializers.CharField(max_length=100, required=False, allow_blank=True)
    area = serializers.CharField(max_length=100, required=False, allow_blank=True)
    estate = serializers.CharField(max_length=100, required=False, allow_blank=True)
    neighbourhood = serializers.CharField(max_length=100, required=False, allow_blank=True)
    min_rent = serializers.IntegerField(min_value=0, required=False)
    max_rent = serializers.IntegerField(min_value=1, required=False)
    bedrooms = serializers.IntegerField(min_value=0, max_value=20, required=False)
    max_bedrooms = serializers.IntegerField(min_value=0, max_value=20, required=False)
    bathrooms = serializers.DecimalField(max_digits=3, decimal_places=1, min_value=0, required=False)
    amenity = serializers.SlugField(max_length=90, required=False)
    amenities = serializers.CharField(max_length=500, required=False, allow_blank=True)
    unit_type = serializers.CharField(max_length=120, required=False, allow_blank=True)
    furnishing = serializers.ChoiceField(choices=Unit.Furnishing.choices, required=False)
    move_in_date = serializers.DateField(required=False)
    verified_only = serializers.BooleanField(required=False, default=False)
    latitude = serializers.FloatField(min_value=-90, max_value=90, required=False)
    longitude = serializers.FloatField(min_value=-180, max_value=180, required=False)
    radius_km = serializers.FloatField(min_value=0.1, max_value=100, required=False)
    ordering = serializers.ChoiceField(choices=tuple(ORDERINGS), required=False)

    def validate_unit_type(self, value):
        types = _csv(value)
        valid = set(Unit.UnitType.values)
        if any(item not in valid for item in types):
            raise serializers.ValidationError("Unknown home type.")
        return types

    def validate_amenities(self, value):
        return [slugify(item) for item in _csv(value)]

    def validate(self, attrs):
        if attrs.get("min_rent", 0) > attrs.get("max_rent", 2**31 - 1):
            raise serializers.ValidationError("Minimum rent must not exceed maximum rent.")
        if "bedrooms" in attrs and "max_bedrooms" in attrs and attrs["bedrooms"] > attrs["max_bedrooms"]:
            raise serializers.ValidationError("Minimum bedrooms must not exceed maximum bedrooms.")
        if ("latitude" in attrs) != ("longitude" in attrs):
            raise serializers.ValidationError("Latitude and longitude must be provided together.")
        if "radius_km" in attrs and "latitude" not in attrs:
            raise serializers.ValidationError("Radius search requires latitude and longitude.")
        # Aliases: town == city, estate/neighbourhood == area.
        attrs["city"] = (attrs.get("city") or attrs.get("town") or "").strip()
        attrs["area"] = (attrs.get("area") or attrs.get("estate") or attrs.get("neighbourhood") or "").strip()
        attrs["q"] = (attrs.get("q") or "").strip()
        ordering = attrs.get("ordering") or ("relevance" if attrs["q"] else "distance" if "latitude" in attrs else "-created_at")
        if ordering == "distance" and "latitude" not in attrs:
            raise serializers.ValidationError("Distance sorting requires your location.")
        attrs["ordering"] = ordering
        return attrs


def _haversine_km(lat1, lon1, lat2, lon2):
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class _AsGeography(Func):
    template = "%(expressions)s::geography"


def _point(longitude, latitude):
    return _AsGeography(Func(Func(Value(float(longitude)), Value(float(latitude)), function="ST_MakePoint"), Value(4326), function="ST_SetSRID"))


def _python_distances(latitude, longitude):
    """{property_id: metres} for SQLite, where PostGIS is unavailable."""
    return {pid: _haversine_km(latitude, longitude, point.latitude, point.longitude) * 1000
            for pid, point in Property.objects.exclude(location__isnull=True).values_list("id", "location")
            if isinstance(point, GeographicPoint)}


def apply_filters(units, params):
    if q := params["q"]:
        for term in q.split()[:5]:
            units = units.filter(Q(title__icontains=term) | Q(property__area__icontains=term) | Q(property__city__icontains=term)
                                 | Q(property__county__icontains=term) | Q(property__name__icontains=term))
    if county := (params.get("county") or "").strip():
        units = units.filter(property__county__iexact=county)
    if params["city"]:
        units = units.filter(property__city__icontains=params["city"])
    if params["area"]:
        units = units.filter(property__area__icontains=params["area"])
    if "min_rent" in params:
        units = units.filter(monthly_rent__gte=params["min_rent"])
    if "max_rent" in params:
        units = units.filter(monthly_rent__lte=params["max_rent"])
    if "bedrooms" in params:
        # 0 means bedsitter/studio exactly; otherwise "at least N".
        units = units.filter(bedrooms=0) if params["bedrooms"] == 0 else units.filter(bedrooms__gte=params["bedrooms"])
    if "max_bedrooms" in params:
        units = units.filter(bedrooms__lte=params["max_bedrooms"])
    if "bathrooms" in params:
        units = units.filter(bathrooms__gte=params["bathrooms"])
    if params.get("unit_type"):
        units = units.filter(unit_type__in=params["unit_type"])
    if "furnishing" in params:
        units = units.filter(furnishing=params["furnishing"])
    if "move_in_date" in params:
        units = units.filter(Q(available_from__isnull=True) | Q(available_from__lte=params["move_in_date"]))
    if params.get("verified_only"):
        units = units.filter(property__verification_status=Property.VerificationStatus.VERIFIED)
    for slug in set(params.get("amenities") or []) | ({params["amenity"]} if params.get("amenity") else set()):
        # One join per amenity: a home must offer every amenity asked for.
        units = units.filter(amenities__slug=slug)

    if "latitude" in params:
        latitude, longitude = params["latitude"], params["longitude"]
        if connection.vendor == "postgresql":
            if "radius_km" in params:
                nearby = Property.objects.extra(
                    where=["ST_DWithin(properties_property.location, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)"],
                    params=[longitude, latitude, params["radius_km"] * 1000],
                ).values("id")
                units = units.filter(property_id__in=nearby)
            units = units.annotate(distance_m=Func(F("property__location"), _point(longitude, latitude), function="ST_Distance", output_field=FloatField()))
        else:
            distances = _python_distances(latitude, longitude)
            if "radius_km" in params:
                units = units.filter(property_id__in=[pid for pid, metres in distances.items() if metres <= params["radius_km"] * 1000])
            units = units.annotate(distance_m=Case(*[When(property_id=pid, then=Value(metres)) for pid, metres in distances.items()],
                                                   default=Value(None), output_field=FloatField()))
    return units


def apply_ordering(units, params):
    """Return (queryset, ordering tuple). Verified listings lead within equal relevance/newness."""
    units = units.annotate(verified_rank=Case(
        When(property__verification_status=Property.VerificationStatus.VERIFIED, then=0), default=1, output_field=IntegerField()))
    ordering = params["ordering"]
    if ordering == "relevance":
        q = params["q"]
        units = units.annotate(match_rank=(
            Case(When(property__area__iexact=q, then=8), When(property__area__istartswith=q, then=5), default=0, output_field=IntegerField())
            + Case(When(property__city__iexact=q, then=4), default=0, output_field=IntegerField())
            + Case(When(property__county__iexact=q, then=2), default=0, output_field=IntegerField())
            + Case(When(title__icontains=q, then=3), default=0, output_field=IntegerField())
        ) * -1)
        fields = ("match_rank", "verified_rank", "-created_at", "id")
    elif ordering == "distance":
        units = units.filter(distance_m__isnull=False)  # homes without a map pin cannot be ranked by distance
        fields = ("distance_m", "verified_rank", "id")
    elif ordering == "-created_at":
        fields = ("verified_rank", "-created_at", "id")
    else:
        fields = (ordering, "verified_rank", "id")
    return units.distinct().order_by(*fields), fields
