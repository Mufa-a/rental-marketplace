from django.contrib import admin

from .models import Amenity, Property, PropertyMedia, Unit


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
