from django.urls import path

from .views import MpesaCallbackView, ReferralFeePaymentView, ViewingCreditWalletView

urlpatterns = [
    path("referral-fees/<int:fee_id>/pay/", ReferralFeePaymentView.as_view(), name="referral-fee-pay"),
    path("viewing-credits/", ViewingCreditWalletView.as_view(), name="viewing-credits"),
    path("mpesa/callback/<str:callback_token>/", MpesaCallbackView.as_view(), name="mpesa-callback"),
]
