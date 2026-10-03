from django.contrib import admin
from django.contrib import messages
from django.db import transaction
from django.utils import timezone

from .models import Amenity, Property, PropertyMedia, Unit


@admin.action(description="Mark selected properties as verified")
def mark_verified(modeladmin, request, queryset):
    eligible = queryset.filter(
        verification_payments__purpose="verification_fee",
        verification_payments__status="successful",
    )
    updated = eligible.update(verification_status=Property.VerificationStatus.VERIFIED, updated_at=timezone.now())
    from .views import _invalidate_public_listing_cache
    transaction.on_commit(_invalidate_public_listing_cache)
    modeladmin.message_user(request, f"{updated} paid property(ies) marked verified.", messages.SUCCESS)


@admin.action(description="Reject verification for selected properties")
def mark_rejected(modeladmin, request, queryset):
    updated = queryset.filter(verification_status=Property.VerificationStatus.PENDING).update(
        verification_status=Property.VerificationStatus.REJECTED, updated_at=timezone.now()
    )
    from .views import _invalidate_public_listing_cache
    transaction.on_commit(_invalidate_public_listing_cache)
    modeladmin.message_user(request, f"{updated} property(ies) rejected.", messages.WARNING)


class UnitInline(admin.TabularInline):
    model = Unit
    extra = 0
    show_change_link = True


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "area", "landlord", "verification_status", "is_active")
    list_filter = ("city", "county", "verification_status", "is_active")
    search_fields = ("name", "address_line", "area", "city", "landlord__user__phone_number")
    inlines = (UnitInline,)
    actions = (mark_verified, mark_rejected)


class PropertyMediaInline(admin.TabularInline):
    model = PropertyMedia
    extra = 0


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("title", "property", "monthly_rent", "bedrooms", "available", "availability_confirmed_at", "is_published")
    list_filter = ("unit_type", "available", "is_published", "furnishing")
    search_fields = ("title", "unit_number", "property__name", "property__area")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("amenities",)
    inlines = (PropertyMediaInline,)
    readonly_fields = ("availability_confirmed_at",)


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon")
    prepopulated_fields = {"slug": ("name",)}
