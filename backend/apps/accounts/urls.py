from django.urls import path

from .views import CookieTokenRefreshView, ConsentView, DeletionRequestView, LogoutView, MeView, MFAVerifyView, OTPRequestView, OTPVerifyView

urlpatterns = [
    path("otp/request/", OTPRequestView.as_view(), name="otp-request"),
    path("otp/verify/", OTPVerifyView.as_view(), name="otp-verify"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("consents/", ConsentView.as_view(), name="consents"),
    path("deletion-request/", DeletionRequestView.as_view(), name="deletion-request"),
    path("token/refresh/", CookieTokenRefreshView.as_view(), name="token-refresh"),
    path("mfa/verify/", MFAVerifyView.as_view(), name="mfa-verify"),
]
