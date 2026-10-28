from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.core.permissions import is_platform_admin
from apps.referrals.services import request_fee_payment

from . import services
from .models import Outcome, Viewing, ViewingRequest
from .serializers import ApprovalSerializer, OutcomeSerializer, ReasonSerializer, RequestSerializer, RescheduleSerializer, ViewingSerializer


def _requests_for(user):
    qs = (ViewingRequest.objects
          .select_related("unit__property__landlord__user", "tenant__user", "viewing")
          .prefetch_related(Prefetch("viewing__outcomes", queryset=Outcome.objects.all())))
    if user.role == User.Role.TENANT:
        return qs.filter(tenant__user=user)
    if user.role == User.Role.LANDLORD:
        return qs.filter(unit__property__landlord__user=user)
    if is_platform_admin(user):
        return qs
    return qs.none()


class RequestListCreateView(APIView):
    """GET: your viewing requests (as tenant or landlord). POST: request a viewing (tenants)."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "viewing_request"

    def get_throttles(self):
        # Only creating requests is rate-limited; reading your own dashboard never is.
        return [ScopedRateThrottle()] if self.request.method == "POST" else []

    def get(self, request):
        items = _requests_for(request.user).order_by("-created_at")
        if status_filter := request.query_params.get("status"):
            items = items.filter(status=status_filter)
        return Response(RequestSerializer(items[:200], many=True, context={"request": request}).data)

    def post(self, request):
        serializer = RequestSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        item = services.create_request(request.user, serializer.validated_data["unit"],
                                       note=serializer.validated_data.get("note", ""),
                                       preferred_times=serializer.validated_data.get("preferred_times"))
        return Response(RequestSerializer(item, context={"request": request}).data, status=201)


class RequestDetailView(APIView):
    """GET /viewings/requests/<id>/ — details, released contact info and the audited booking timeline."""

    permission_classes = [IsAuthenticated]

    def get(self, request, request_id):
        item = get_object_or_404(_requests_for(request.user), pk=request_id)
        data = RequestSerializer(item, context={"request": request}).data
        data["timeline"] = services.timeline(item)
        return Response(data)


class RequestActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id, action):
        if not ViewingRequest.objects.filter(pk=request_id).exists():
            return Response({"error": {"code": "not_found", "message": "Viewing request not found."}}, status=404)
        context = {"request": request}
        if action == "cancel":
            reason = ReasonSerializer(data=request.data); reason.is_valid(raise_exception=True)
            item = services.cancel_request(request_id, request.user, reason=reason.validated_data["reason"] or reason.validated_data["note"])
            return Response(RequestSerializer(item, context=context).data)
        if action == "reject":
            reason = ReasonSerializer(data=request.data); reason.is_valid(raise_exception=True)
            item = services.reject_request(request_id, request.user, note=reason.validated_data["note"] or reason.validated_data["reason"])
            return Response(RequestSerializer(item, context=context).data)
        if action == "approve":
            item = ViewingRequest.objects.select_related("unit__property").get(pk=request_id)
            if not services.is_landlord_for(request.user, item) and not is_platform_admin(request.user):
                raise PermissionDenied("Only the listing landlord can act on this request.")
            serializer = ApprovalSerializer(data=request.data); serializer.is_valid(raise_exception=True)
            viewing = services.approve_request(request_id, request.user, scheduled_at=serializer.validated_data["scheduled_at"],
                                               meeting_note=serializer.validated_data.get("meeting_note", ""))
            return Response(ViewingSerializer(viewing, context=context).data, status=201)
        raise ValidationError("Unknown action.")


class ViewingActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, viewing_id, action):
        viewing = get_object_or_404(Viewing.objects.select_related("request__unit__property__landlord", "request__tenant"), pk=viewing_id)
        if services.party_for(request.user, viewing.request) is None:
            raise PermissionDenied("You are not involved in this viewing.")
        context = {"request": request}
        if action == "complete":
            return Response(ViewingSerializer(services.complete_viewing(viewing_id, request.user), context=context).data)
        if action == "reschedule":
            serializer = RescheduleSerializer(data=request.data); serializer.is_valid(raise_exception=True)
            updated = services.reschedule_viewing(viewing_id, request.user, scheduled_at=serializer.validated_data["scheduled_at"],
                                                  meeting_note=serializer.validated_data.get("meeting_note"))
            return Response(ViewingSerializer(updated, context=context).data)
        if action == "outcome":
            serializer = OutcomeSerializer(data=request.data); serializer.is_valid(raise_exception=True)
            outcome, created, fee = services.report_outcome(viewing_id, request.user, choice=serializer.validated_data["choice"],
                                                            note=serializer.validated_data.get("note", ""))
            data = OutcomeSerializer(outcome).data
            if fee is not None and fee.status == fee.Status.PENDING and request.user.role == User.Role.LANDLORD:
                # Outside the outcome transaction: the STK prompt is a network call and may fail independently.
                payment = request_fee_payment(fee, request.user)
                data["fee"] = {"id": fee.pk, "amount": fee.amount, "currency": fee.currency, "due_at": fee.due_at}
                data["payment_status"] = payment.status if payment else "not_started"
            return Response(data, status=201 if created else 200)
        raise ValidationError("Unknown action.")
