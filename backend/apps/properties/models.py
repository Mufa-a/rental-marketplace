"""The unit-level listings domain."""
from django.db import models
from django.core.validators import MinValueValidator
from django.utils.text import slugify
from django.contrib.postgres.indexes import GistIndex

from .fields import PointField


class Amenity(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    icon = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ("name",)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Property(models.Model):
    class VerificationStatus(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        PENDING = "pending", "Verification pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    landlord = models.ForeignKey("accounts.LandlordProfile", on_delete=models.PROTECT, related_name="properties")
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    address_line = models.CharField(max_length=255)
    area = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    county = models.CharField(max_length=100)
    country = models.CharField(max_length=2, default="KE")
    location = PointField(geography=True, srid=4326, null=True, blank=True)
    verification_status = models.CharField(max_length=12, choices=VerificationStatus.choices, default=VerificationStatus.UNVERIFIED)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["city", "area", "is_active"], name="properties__city_26452e_idx"),
            GistIndex(fields=["location"], name="properties_location_gist"),
        ]
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.name} - {self.area}, {self.city}"


class Unit(models.Model):
    class UnitType(models.TextChoices):
        BEDSITTER = "bedsitter", "Bedsitter"
        STUDIO = "studio", "Studio"
        APARTMENT = "apartment", "Apartment"
        HOUSE = "house", "House"
        MAISONETTE = "maisonette", "Maisonette"
        ROOM = "room", "Room"

    class Furnishing(models.TextChoices):
        UNFURNISHED = "unfurnished", "Unfurnished"
        SEMI_FURNISHED = "semi_furnished", "Semi-furnished"
        FURNISHED = "furnished", "Furnished"

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="units")
    unit_number = models.CharField(max_length=50)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    unit_type = models.CharField(max_length=15, choices=UnitType.choices)
    monthly_rent = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    security_deposit = models.PositiveIntegerField(default=0)
    bedrooms = models.PositiveSmallIntegerField(default=0)
    bathrooms = models.DecimalField(max_digits=3, decimal_places=1, default=1)
    floor_area_sqm = models.PositiveIntegerField(null=True, blank=True)
    furnishing = models.CharField(max_length=16, choices=Furnishing.choices, default=Furnishing.UNFURNISHED)
    available = models.BooleanField(default=True)
    availability_confirmed_at = models.DateTimeField(null=True, blank=True)
    available_from = models.DateField(null=True, blank=True)
    is_published = models.BooleanField(default=False)
    amenities = models.ManyToManyField(Amenity, blank=True, related_name="units")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["property", "unit_number"], name="unique_unit_number_per_property")]
        indexes = [
            models.Index(fields=["available", "is_published"], name="properties__availab_9610c6_idx"),
            models.Index(fields=["monthly_rent", "bedrooms"], name="properties__monthly_66e9ee_idx"),
        ]
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        previous_available = None
        if not self._state.adding:
            previous_available = Unit.objects.filter(pk=self.pk).values_list("available", flat=True).first()
        availability_changed = self._state.adding or previous_available != self.available
        if (availability_changed
                or (self.available and self.availability_confirmed_at is None)):
            from django.utils import timezone
            self.availability_confirmed_at = timezone.now()
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"availability_confirmed_at"}
        if not self.slug:
            base = slugify(f"{self.property.city}-{self.property.area}-{self.title}-{self.unit_number}")
            candidate, number = base[:220], 2
            while Unit.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                suffix = f"-{number}"
                candidate = f"{base[:220 - len(suffix)]}{suffix}"
                number += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.property.name} - {self.unit_number}"


class PropertyMedia(models.Model):
    class MediaType(models.TextChoices):
        EXTERIOR = "exterior", "Exterior"
        LIVING_ROOM = "living_room", "Living room"
        BEDROOM = "bedroom", "Bedroom"
        KITCHEN = "kitchen", "Kitchen"
        BATHROOM = "bathroom", "Bathroom"
        OTHER = "other", "Other"

    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="media")
    asset_key = models.CharField(max_length=500, unique=True)
    media_type = models.CharField(max_length=20, choices=MediaType.choices, default=MediaType.OTHER)
    alt_text = models.CharField(max_length=180, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sort_order", "created_at")

    def __str__(self):
        return f"{self.unit} ({self.media_type})"


class SavedUnit(models.Model):
    tenant = models.ForeignKey("accounts.TenantProfile", on_delete=models.CASCADE, related_name="saved_units")
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="saved_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("tenant", "unit"), name="unique_saved_unit_per_tenant")]
        ordering = ("-created_at",)
