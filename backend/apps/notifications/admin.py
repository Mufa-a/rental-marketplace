from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("event", "recipient", "status", "attempt_count", "created_at", "sent_at")
    list_filter = ("status", "event")
    search_fields = ("recipient__phone_number", "dedupe_key", "provider_reference")
    readonly_fields = ("recipient", "event", "dedupe_key", "message", "status", "attempt_count", "provider_reference", "last_error", "created_at", "sent_at")

    def has_add_permission(self, request):
        return False
