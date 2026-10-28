from django.urls import path

from .views import (
    MpesaCallbackView, MyPaymentListView, PaymentDetailView, PriceListView, PropertyVerificationPaymentView,
    ReferralFeePaymentView, ViewingCreditWalletView,
)

urlpatterns = [
    path("prices/", PriceListView.as_view(), name="price-list"),
    path("mine/", MyPaymentListView.as_view(), name="my-payments"),
    path("<int:payment_id>/", PaymentDetailView.as_view(), name="payment-detail"),
    path("referral-fees/<int:fee_id>/pay/", ReferralFeePaymentView.as_view(), name="referral-fee-pay"),
    path("viewing-credits/", ViewingCreditWalletView.as_view(), name="viewing-credits"),
    path("property-verification/<int:property_id>/pay/", PropertyVerificationPaymentView.as_view(), name="property-verification-pay"),
    path("mpesa/callback/<str:callback_token>/", MpesaCallbackView.as_view(), name="mpesa-callback"),
]
