from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import LandlordProfile, TenantProfile, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("phone_number", "username", "role", "phone_verified", "is_active")
    list_filter = ("role", "phone_verified", "is_active")
    search_fields = ("phone_number", "username", "email")
    ordering = ("-date_joined",)


admin.site.register(TenantProfile)
admin.site.register(LandlordProfile)
