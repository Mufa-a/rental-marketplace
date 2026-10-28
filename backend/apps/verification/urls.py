from django.urls import path

from .views import LandlordVerificationView

urlpatterns = [path("landlord/", LandlordVerificationView.as_view(), name="landlord-verification")]
