from django.urls import path

from .views import ConsentView, DeletionRequestView, LogoutView, MeView, OTPRequestView, OTPVerifyView, TokenRefreshView

urlpatterns = [
    path("otp/request/", OTPRequestView.as_view(), name="otp-request"),
    path("otp/verify/", OTPVerifyView.as_view(), name="otp-verify"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("consents/", ConsentView.as_view(), name="consents"),
    path("deletion-request/", DeletionRequestView.as_view(), name="deletion-request"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
]
