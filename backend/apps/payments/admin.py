from django.contrib import admin
from .models import Payment, ViewingCreditPurchase, ViewingCreditUse
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin): list_display=("provider_reference","amount","status","phone_number","created_at"); list_filter=("status",); search_fields=("provider_reference","phone_number")

admin.site.register(ViewingCreditPurchase)
admin.site.register(ViewingCreditUse)
