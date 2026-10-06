from django.contrib import admin, messages
from django.utils import timezone

from . import services
from .models import AccountRestriction, Dispute, Report


class OpenFilter(admin.SimpleListFilter):
    title = "state"
    parameter_name = "state"

    def lookups(self, request, model_admin):
        return (("open", "Open"), ("resolved", "Resolved"))

    def queryset(self, request, queryset):
        if self.value() == "open":
            return queryset.filter(resolved_at__isnull=True)
        if self.value() == "resolved":
            return queryset.filter(resolved_at__isnull=False)
        return queryset


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "reason", "reported_user", "reporter", "created_at", "resolution")
    list_filter = (OpenFilter, "reason", "resolution")
    search_fields = ("reported_user__phone_number", "reporter__phone_number", "detail")
    readonly_fields = ("reporter", "reported_user", "listing", "reason", "detail", "created_at", "resolved_at", "resolved_by")
    actions = ("dismiss_reports", "hide_listings_and_resolve", "suspend_landlord_and_resolve")

    @admin.action(description="Dismiss selected reports (no action taken)")
    def dismiss_reports(self, request, queryset):
        n = services.resolve_reports(queryset, Report.Resolution.DISMISSED, request.user)
        self.message_user(request, f"Dismissed {n} report(s).")

    @admin.action(description="Hide reported listings and mark reports actioned")
    def hide_listings_and_resolve(self, request, queryset):
        hidden = services.hide_reported_listings(queryset, request.user)
        n = services.resolve_reports(queryset, Report.Resolution.ACTIONED, request.user)
        self.message_user(request, f"Hid {hidden} listing(s); actioned {n} report(s).")

    @admin.action(description="Suspend reported landlord(s), hide all their listings, mark actioned")
    def suspend_landlord_and_resolve(self, request, queryset):
        users = {r.reported_user for r in queryset if r.reported_user_id}
        users.discard(None)
        if any(u.is_superuser or u.is_staff or u.role == "admin" for u in users):
            self.message_user(request, "Staff accounts cannot be suspended from here.", level=messages.ERROR)
            return
        for user in users:
            services.suspend_landlord(user, "Suspended after reports reviewed by admin", request.user)
        reports = Report.objects.filter(reported_user__in=users)
        n = services.resolve_reports(reports, Report.Resolution.ACTIONED, request.user)
        self.message_user(request, f"Suspended {len(users)} account(s); actioned {n} report(s).")

    def has_add_permission(self, request):
        return False


@admin.register(AccountRestriction)
class AccountRestrictionAdmin(admin.ModelAdmin):
    list_display = ("user", "reason", "created_at", "expires_at")
    search_fields = ("user__phone_number", "reason")
    actions = ("lift_suspension",)

    @admin.action(description="Lift suspension (reactivate account and clear listing holds)")
    def lift_suspension(self, request, queryset):
        for user in {r.user for r in queryset}:
            services.lift_suspension(user, request.user)
        self.message_user(request, "Suspension lifted. Listings stay unpublished until the landlord republishes them.")


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin): list_display=("id","viewing","status","opened_by","created_at"); list_filter=("status",)
