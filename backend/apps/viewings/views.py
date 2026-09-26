from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from apps.accounts.models import TenantProfile, User
from apps.core.models import AuditLog
from apps.properties.models import Unit
from apps.trust.models import Dispute
from apps.notifications.services import queue_sms
from apps.payments.services import reserve_viewing_credit, settle_viewing_credit
from .models import Outcome, Viewing, ViewingRequest
from .serializers import ApprovalSerializer, OutcomeSerializer, RequestSerializer, ViewingSerializer

def audit(request, action, obj):
    AuditLog.objects.create(actor=request.user, action=action, object_type=obj._meta.label, object_id=str(obj.pk))

def is_landlord_for(user, request):
    return user.role == User.Role.ADMIN or request.unit.property.landlord.user_id == user.id

class RequestListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "viewing_request"
    def get(self, request):
        qs = ViewingRequest.objects.select_related("unit__property__landlord__user", "viewing")
        if request.user.role == User.Role.TENANT: qs = qs.filter(tenant__user=request.user)
        elif request.user.role == User.Role.LANDLORD: qs = qs.filter(unit__property__landlord__user=request.user)
        return Response(RequestSerializer(qs, many=True).data)
    @transaction.atomic
    def post(self, request):
        if request.user.role != User.Role.TENANT: raise PermissionDenied("Only tenants can request viewings.")
        tenant = TenantProfile.objects.get_or_create(user=request.user)[0]
        if ViewingRequest.objects.filter(tenant=tenant, status__in=["pending_landlord", "approved"]).count() >= 3:
            raise ValidationError("You have reached the maximum of three active viewing requests.")
        serializer = RequestSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        unit = serializer.validated_data["unit"]
        if (not unit.available or not unit.is_published or not unit.availability_confirmed_at
                or unit.availability_confirmed_at < timezone.now() - timedelta(days=30)):
            raise ValidationError("This unit is not recently confirmed as available for viewings.")
        viewing_request = serializer.save(tenant=tenant)
        reserve_viewing_credit(viewing_request)
        audit(request, "viewing_request.created", viewing_request)
        landlord_user = unit.property.landlord.user
        queue_sms(recipient=landlord_user, event="viewing.requested", dedupe_key=f"viewing-request:{viewing_request.pk}:landlord", message=f"A tenant requested a viewing for {unit.title}. Sign in to approve or decline the request.")
        return Response(RequestSerializer(viewing_request).data, status=201)

class RequestActionView(APIView):
    permission_classes = [IsAuthenticated]
    @transaction.atomic
    def post(self, request, request_id, action):
        item = get_object_or_404(ViewingRequest.objects.select_related("unit__property__landlord__user"), pk=request_id)
        if action == "cancel":
            if item.tenant.user_id != request.user.id or item.status not in ["pending_landlord", "approved"]: raise PermissionDenied("This request cannot be cancelled.")
            was_pending = item.status == ViewingRequest.Status.PENDING
            item.status = ViewingRequest.Status.CANCELLED; item.save(update_fields=["status", "updated_at"])
            if was_pending:
                settle_viewing_credit(item, restore=True)
            if hasattr(item, "viewing"):
                item.viewing.status = Viewing.Status.CANCELLED
                item.viewing.save(update_fields=["status", "updated_at"])
            audit(request, "viewing_request.cancelled", item); return Response(RequestSerializer(item).data)
        if not is_landlord_for(request.user, item): raise PermissionDenied("Only the listing landlord can act on this request.")
        if action == "reject":
            if item.status != ViewingRequest.Status.PENDING: raise ValidationError("Only pending requests may be rejected.")
            item.status = ViewingRequest.Status.REJECTED; item.landlord_note = request.data.get("note", ""); item.save(); audit(request, "viewing_request.rejected", item)
            settle_viewing_credit(item, restore=True)
            queue_sms(recipient=item.tenant.user, event="viewing.rejected", dedupe_key=f"viewing-request:{item.pk}:rejected:tenant", message=f"Your viewing request for {item.unit.title} was declined. Browse other available homes in the area.")
            return Response(RequestSerializer(item).data)
        if action == "approve":
            if item.status != ViewingRequest.Status.PENDING: raise ValidationError("Only pending requests may be approved.")
            if (not item.unit.available or not item.unit.is_published or not item.unit.availability_confirmed_at
                    or item.unit.availability_confirmed_at < timezone.now() - timedelta(days=30)):
                raise ValidationError("This home is no longer recently confirmed as available for viewings.")
            serializer = ApprovalSerializer(data=request.data); serializer.is_valid(raise_exception=True)
            if serializer.validated_data["scheduled_at"] <= timezone.now():
                raise ValidationError({"scheduled_at": "Choose a future viewing time."})
            item.status = ViewingRequest.Status.APPROVED; item.save()
            settle_viewing_credit(item)
            viewing = Viewing.objects.create(request=item, scheduled_at=serializer.validated_data["scheduled_at"], meeting_note=serializer.validated_data.get("meeting_note", "")); audit(request, "viewing.scheduled", viewing)
            when = timezone.localtime(viewing.scheduled_at).strftime("%d %b, %I:%M %p")
            queue_sms(recipient=item.tenant.user, event="viewing.approved", dedupe_key=f"viewing:{viewing.pk}:approved:tenant", message=f"Your viewing for {item.unit.title} was approved for {when}.")
            return Response(ViewingSerializer(viewing).data, status=201)
        raise ValidationError("Unknown action.")

class ViewingActionView(APIView):
    permission_classes = [IsAuthenticated]
    @transaction.atomic
    def post(self, request, viewing_id, action):
        viewing = get_object_or_404(Viewing.objects.select_related("request__unit__property__landlord__user", "request__tenant__user"), pk=viewing_id)
        involved = viewing.request.tenant.user_id == request.user.id or is_landlord_for(request.user, viewing.request)
        if not involved: raise PermissionDenied("You are not involved in this viewing.")
        if action == "complete":
            if viewing.status != Viewing.Status.SCHEDULED: raise ValidationError("Only scheduled viewings may be completed.")
            viewing.status = Viewing.Status.OUTCOME_PENDING; viewing.completed_at = timezone.now(); viewing.save(); audit(request, "viewing.completed", viewing); return Response(ViewingSerializer(viewing).data)
        if action == "outcome":
            if viewing.status == Viewing.Status.SCHEDULED and viewing.scheduled_at <= timezone.now():
                viewing.status = Viewing.Status.OUTCOME_PENDING
                viewing.completed_at = timezone.now()
                viewing.save(update_fields=["status", "completed_at", "updated_at"])
            if viewing.status not in [Viewing.Status.OUTCOME_PENDING, Viewing.Status.STILL_DECIDING]: raise ValidationError("An outcome is not due for this viewing.")
            serializer = OutcomeSerializer(data=request.data); serializer.is_valid(raise_exception=True)
            if request.user.role == User.Role.ADMIN:
                raise PermissionDenied("Only the viewing tenant and landlord may report an outcome.")
            outcome, created = Outcome.objects.update_or_create(viewing=viewing, reporter=request.user, defaults={"choice": serializer.validated_data["choice"], "note": serializer.validated_data.get("note", "")})
            choices = set(viewing.outcomes.values_list("choice", flat=True))
            outcome_count = viewing.outcomes.count()
            landlord_reported_rented = request.user.role == User.Role.LANDLORD and outcome.choice == Outcome.Choice.RENTED
            if landlord_reported_rented:
                viewing.status = Viewing.Status.RENTED
            elif Outcome.Choice.DISPUTED in choices or (outcome_count == 2 and len(choices) > 1):
                viewing.status = Viewing.Status.DISPUTED
                dispute_reason = "A party disputed the viewing outcome." if Outcome.Choice.DISPUTED in choices else "The tenant and landlord reported different outcomes."
                dispute, created_dispute = Dispute.objects.get_or_create(
                    viewing=viewing,
                    defaults={"opened_by": request.user, "reason": dispute_reason},
                )
                if created_dispute:
                    audit(request, "viewing.dispute_opened", dispute)
            elif outcome_count < 2:
                # Keep the second party able to report when the first report was not a
                # landlord rental confirmation.
                viewing.status = Viewing.Status.OUTCOME_PENDING
            else:
                viewing.status = serializer.validated_data["choice"]
            viewing.save(update_fields=["status", "updated_at"]); audit(request, "viewing.outcome_reported", outcome)
            if landlord_reported_rented:
                from apps.referrals.services import create_fee_for_rented_viewing
                fee, _ = create_fee_for_rented_viewing(viewing)
                unit = viewing.request.unit
                unit.available = False
                unit.is_published = False
                unit.availability_confirmed_at = timezone.now()
                unit.save(update_fields=["available", "is_published", "availability_confirmed_at", "updated_at"])
                queue_sms(recipient=unit.property.landlord.user, event="referral.fee_created", dedupe_key=f"referral-fee:{fee.pk}:landlord", message=f"You reported that {unit.title} was rented. A KSh {fee.amount:,} success fee is due by {timezone.localtime(fee.due_at).strftime('%d %b')}. Approve the M-Pesa prompt sent to your registered number.")
                from apps.payments.models import Payment
                from apps.payments.views import initiate_referral_fee_push
                from uuid import uuid4
                payment, payment_created = Payment.objects.get_or_create(
                    idempotency_key=f"referral-auto:{fee.pk}",
                    defaults={"fee": fee, "purpose": Payment.Purpose.REFERRAL_FEE,
                              "amount": fee.amount, "phone_number": unit.property.landlord.user.phone_number,
                              "provider_reference": f"pending:{uuid4().hex}"},
                )
                if payment.fee_id != fee.pk:
                    raise ValidationError("The rental fee payment reference is inconsistent. Contact support.")
                from apps.properties.views import _invalidate_public_listing_cache
                _invalidate_public_listing_cache()
                response = Response({**OutcomeSerializer(outcome).data, "payment_status": payment.status}, status=201 if created else 200)
                if payment_created:
                    def start_payment_prompt():
                        initiate_referral_fee_push(payment.pk, request.user.pk)
                        payment.refresh_from_db()
                        response.data["payment_status"] = payment.status
                        response.data["payment_message"] = payment.provider_payload.get("customer_message") or payment.provider_payload.get("error", "")
                    transaction.on_commit(start_payment_prompt, robust=True)
                return response
            return Response(OutcomeSerializer(outcome).data, status=201 if created else 200)
        raise ValidationError("Unknown action.")
