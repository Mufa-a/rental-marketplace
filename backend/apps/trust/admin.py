from django.contrib import admin
from .models import AccountRestriction, Dispute, Report
admin.site.register(Report)
admin.site.register(AccountRestriction)
@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin): list_display=("id","viewing","status","opened_by","created_at"); list_filter=("status",)
