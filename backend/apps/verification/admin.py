from django.contrib import admin

from .models import LandlordVerification, VerificationDocument


class DocumentInline(admin.TabularInline):
    model = VerificationDocument
    extra = 0
    # Documents are opened through the audited admin API, not Django admin file links.
    fields = ("kind", "content_type", "size", "uploaded_at")
    readonly_fields = fields
    can_delete = False


@admin.register(LandlordVerification)
class LandlordVerificationAdmin(admin.ModelAdmin):
    list_display = ("id", "landlord", "status", "relationship", "submitted_at", "reviewed_at")
    list_filter = ("status", "relationship")
    readonly_fields = ("landlord", "legal_name", "id_type", "id_last4", "relationship", "agency_name", "submitted_at",
                       "reviewed_by", "reviewed_at", "documents_purged_at")
    inlines = (DocumentInline,)

    def has_add_permission(self, request):
        return False
