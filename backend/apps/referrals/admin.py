from django.contrib import admin
from .models import ReferralAttribution, ReferralFee
admin.site.register(ReferralAttribution)
@admin.register(ReferralFee)
class ReferralFeeAdmin(admin.ModelAdmin): list_display=("id","amount","status","due_at","created_at"); list_filter=("status",)
