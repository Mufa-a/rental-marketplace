from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.payments.models import Payment
from apps.properties.models import Property, Unit
from apps.referrals.models import ReferralFee
from apps.viewings.models import Outcome, Viewing, ViewingRequest


class AdminOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != User.Role.ADMIN or not request.user.is_staff:
            return Response({"error": {"code": "admin_only", "message": "Admin access is required."}}, status=403)

        latest_requests = ViewingRequest.objects.select_related(
            "tenant__user", "unit__property__landlord__user", "unit"
        ).order_by("-created_at")[:12]
        latest_fees = ReferralFee.objects.select_related(
            "attribution__landlord__user", "attribution__viewing__request__unit"
        ).order_by("-created_at")[:12]
        latest_payments = Payment.objects.select_related(
            "fee__attribution__landlord__user", "tenant_user"
        ).order_by("-created_at")[:12]
        latest_viewings = Viewing.objects.select_related(
            "request__unit__property", "request__tenant__user"
        ).prefetch_related("outcomes").order_by("-created_at")[:12]

        return Response({
            "metrics": {
                "tenants": User.objects.filter(role=User.Role.TENANT).count(),
                "landlords": User.objects.filter(role=User.Role.LANDLORD).count(),
                "properties": Property.objects.count(),
                "units": Unit.objects.count(),
                "active_listings": Unit.objects.filter(available=True, is_published=True, property__is_active=True).count(),
                "viewing_requests": ViewingRequest.objects.count(),
                "pending_viewings": Viewing.objects.filter(
                    Q(status=Viewing.Status.OUTCOME_PENDING)
                    | Q(status=Viewing.Status.SCHEDULED, scheduled_at__lte=timezone.now())
                ).count(),
                "rentals_reported": Viewing.objects.filter(status=Viewing.Status.RENTED).count(),
                "fees_due": ReferralFee.objects.filter(status=ReferralFee.Status.PENDING).count(),
                "fees_collected_ksh": Payment.objects.filter(
                    purpose=Payment.Purpose.REFERRAL_FEE, status=Payment.Status.SUCCESSFUL
                ).aggregate(total=Sum("amount"))["total"] or 0,
                "bundle_revenue_ksh": Payment.objects.filter(
                    purpose=Payment.Purpose.VIEWING_CREDITS, status=Payment.Status.SUCCESSFUL
                ).aggregate(total=Sum("amount"))["total"] or 0,
                "failed_payments": Payment.objects.filter(status=Payment.Status.FAILED).count(),
            },
            "viewing_requests": [{
                "id": item.pk, "status": item.status, "unit": item.unit.title,
                "property": item.unit.property.name, "tenant": item.tenant.user.phone_number,
                "landlord": item.unit.property.landlord.user.phone_number,
                "rent": item.unit.monthly_rent, "created_at": item.created_at,
            } for item in latest_requests],
            "viewings": [{
                "id": item.pk, "status": item.status, "unit": item.request.unit.title,
                "property": item.request.unit.property.name,
                "scheduled_at": item.scheduled_at,
                "outcomes": [{"reporter": outcome.reporter.phone_number, "choice": outcome.choice}
                             for outcome in item.outcomes.all()],
            } for item in latest_viewings],
            "fees": [{
                "id": fee.pk, "amount": fee.amount, "status": fee.status,
                "unit": fee.attribution.viewing.request.unit.title,
                "landlord": fee.attribution.landlord.user.phone_number,
                "due_at": fee.due_at, "created_at": fee.created_at,
            } for fee in latest_fees],
            "payments": [{
                "id": payment.pk, "purpose": payment.purpose, "amount": payment.amount,
                "status": payment.status, "phone_number": payment.phone_number,
                "payer": payment.fee.attribution.landlord.user.phone_number if payment.fee_id else payment.tenant_user.phone_number,
                "created_at": payment.created_at,
            } for payment in latest_payments],
        })
