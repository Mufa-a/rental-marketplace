from django.urls import path

from .views import MyReferralFeeListView

urlpatterns = [path("mine/", MyReferralFeeListView.as_view(), name="my-referral-fees")]
