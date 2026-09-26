from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from .models import ReferralFee


class ReferralFeeSerializer(serializers.ModelSerializer):
    viewing_id = serializers.IntegerField(source="attribution.viewing_id", read_only=True)
    unit_title = serializers.CharField(source="attribution.viewing.request.unit.title", read_only=True)

    class Meta:
        model = ReferralFee
        fields = ("id", "viewing_id", "unit_title", "amount", "status", "due_at", "created_at")


class MyReferralFeeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        fees = ReferralFee.objects.select_related("attribution__viewing__request__unit").order_by("-created_at")
        if request.user.role == User.Role.LANDLORD:
            fees = fees.filter(attribution__landlord__user=request.user)
        elif request.user.role != User.Role.ADMIN:
            raise PermissionDenied("Only landlords can view referral fees.")
        return Response(ReferralFeeSerializer(fees, many=True).data)
