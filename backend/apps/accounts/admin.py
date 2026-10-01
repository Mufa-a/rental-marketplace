from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from django.utils import timezone

from apps.core.models import AuditLog
from .models import AccountDeletionRequest, ConsentRecord, LandlordProfile, TenantProfile, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("phone_number", "username", "role", "phone_verified", "is_active")
    list_filter = ("role", "phone_verified", "is_active")
    search_fields = ("phone_number", "username", "email")
    ordering = ("-date_joined",)


admin.site.register(TenantProfile)
admin.site.register(LandlordProfile)


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "consent_type", "granted", "policy_version", "created_at")
    list_filter = ("consent_type", "granted", "policy_version")
    readonly_fields = ("user", "consent_type", "granted", "policy_version", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AccountDeletionRequest)
class AccountDeletionRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "phone_last4", "role", "status", "requested_at", "resolved_at")
    list_filter = ("status", "role")
    readonly_fields = ("user", "phone_last4", "role", "reason", "requested_at")
    actions = ("mark_completed", "mark_rejected")

    def _resolve(self, request, queryset, status, label):
        pending = queryset.filter(status=AccountDeletionRequest.Status.PENDING)
        for item in pending:
            item.status = status
            item.resolved_at = timezone.now()
            item.save(update_fields=["status", "resolved_at"])
            AuditLog.objects.create(actor=request.user, action=f"account.deletion_{status}", object_type=item._meta.label, object_id=str(item.pk))
        self.message_user(request, f"{pending.count()} request(s) marked {label}. Remember that marking a request does not delete the account; do that separately.")

    @admin.action(description="Mark selected pending requests as completed (after deleting/anonymising the account)")
    def mark_completed(self, request, queryset):
        self._resolve(request, queryset, AccountDeletionRequest.Status.COMPLETED, "completed")

    @admin.action(description="Mark selected pending requests as rejected / data retained")
    def mark_rejected(self, request, queryset):
        self._resolve(request, queryset, AccountDeletionRequest.Status.REJECTED, "rejected")
