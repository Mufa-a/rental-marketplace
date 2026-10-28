"""Administrator API: moderation queues, verification review, payments, pricing, audit and reports.

Every endpoint requires IsPlatformAdmin (active staff account with the admin role),
enforced here on the server. Every state change is written to the audit log with the
acting administrator. Phone numbers are masked in lists; administrators see full
contact details only on the specific record they open, and that access is logged.
"""
import csv
from datetime import timedelta

from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.core.exceptions import Conflict
from apps.core.models import AuditLog, verify_audit_chain
from apps.core.permissions import IsPlatformAdmin
from apps.notifications.services import notify
from apps.payments import services as payment_services
from apps.payments.models import Payment, ReferralFeeRule, ServicePrice, ViewingPackage
from apps.properties.models import Property, Unit, UnitDailyStat
from apps.properties.search import listing_path, public_units
from apps.referrals.models import ReferralFee, ReferralFlag
from apps.referrals.services import mark_unit_occupied, resolve_flag_or_dispute
from apps.trust import services as trust_services
from apps.trust.models import Dispute, Report
from apps.verification import services as verification_services
from apps.verification.models import LandlordVerification, VerificationDocument
from apps.viewings.models import Viewing, ViewingRequest


def mask_phone(phone):
    phone = phone or ""
    return f"{phone[:5]}{'•' * max(len(phone) - 7, 0)}{phone[-2:]}" if len(phone) > 7 else "•••"


def audit(request, action, obj=None, **metadata):
    AuditLog.objects.create(actor=request.user, action=action, object_type=obj._meta.label if obj is not None else "admin",
                            object_id=str(obj.pk) if obj is not None else "-", metadata=metadata)


class AdminPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminView(APIView):
    permission_classes = [IsPlatformAdmin]

    def paginate(self, queryset, rows):
        paginator = AdminPagination()
        page = paginator.paginate_queryset(queryset, self.request, view=self)
        return paginator.get_paginated_response([rows(item) for item in page])


def _bust():
    from apps.properties.views import _invalidate_public_listing_cache
    transaction.on_commit(_invalidate_public_listing_cache)


# ------------------------------------------------------------------ listings

def _listing_row(unit):
    prop = unit.property
    return {
        "id": unit.pk, "title": unit.title, "property": prop.name, "area": prop.area, "city": prop.city, "county": prop.county,
        "monthly_rent": unit.monthly_rent, "bedrooms": unit.bedrooms, "unit_type": unit.unit_type,
        "available": unit.available, "is_published": unit.is_published, "moderation_status": unit.moderation_status,
        "moderation_note": unit.moderation_note, "moderation_hold": unit.moderation_hold,
        "verification_status": prop.verification_status, "property_id": prop.pk,
        "landlord": mask_phone(prop.landlord.user.phone_number), "landlord_verified": prop.landlord.verification_tier != "basic",
        "possible_duplicate_of": unit.possible_duplicate_of_id, "open_reports": getattr(unit, "open_reports", 0),
        "media_count": getattr(unit, "media_count", 0),
        "path": listing_path(unit), "created_at": unit.created_at,
    }


class AdminListingListView(AdminView):
    """GET /admin/listings/?moderation_status=&q=&hold=true&reported=true"""

    def get(self, request):
        units = (Unit.objects.select_related("property__landlord__user")
                 .annotate(open_reports=Count("report", filter=Q(report__resolved_at__isnull=True), distinct=True),
                           media_count=Count("media", distinct=True)))
        if status := request.query_params.get("moderation_status"):
            units = units.filter(moderation_status=status)
        if request.query_params.get("hold") == "true":
            units = units.filter(moderation_hold=True)
        if request.query_params.get("reported") == "true":
            units = units.filter(open_reports__gt=0)
        if q := request.query_params.get("q", "").strip():
            units = units.filter(Q(title__icontains=q) | Q(property__name__icontains=q) | Q(property__area__icontains=q)
                                 | Q(property__landlord__user__phone_number__icontains=q))
        return self.paginate(units.order_by("created_at" if status == "pending_review" else "-created_at", "id"), _listing_row)


class ModerationSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("approve", "reject", "request_changes", "hide", "unhide", "mark_occupied"))
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class AdminListingModerateView(AdminView):
    """POST /admin/listings/<id>/moderate/ {action, note}"""

    @transaction.atomic
    def post(self, request, unit_id):
        unit = get_object_or_404(Unit.objects.select_for_update().select_related("property__landlord__user"), pk=unit_id)
        serializer = ModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action, note = serializer.validated_data["action"], serializer.validated_data["note"]
        if action in ("reject", "request_changes") and not note.strip():
            raise ValidationError({"note": "Tell the landlord what to fix."})
        status = Unit.ModerationStatus
        if action == "approve":
            unit.moderation_status, unit.moderation_note = status.APPROVED, note
        elif action == "reject":
            unit.moderation_status, unit.moderation_note, unit.is_published = status.REJECTED, note, False
        elif action == "request_changes":
            unit.moderation_status, unit.moderation_note = status.CHANGES_REQUESTED, note
        elif action == "hide":
            unit.moderation_hold, unit.is_published = True, False
        elif action == "unhide":
            unit.moderation_hold = False
        if action == "mark_occupied":
            mark_unit_occupied(unit)
        else:
            unit.save()
        audit(request, f"unit.moderation.{action}", unit, note=note[:200])
        landlord = unit.property.landlord.user
        messages = {
            "approve": f"Your listing \"{unit.title}\" was approved and can appear in search.",
            "reject": f"Your listing \"{unit.title}\" was not approved: {note}",
            "request_changes": f"Please update your listing \"{unit.title}\": {note}",
            "hide": f"Your listing \"{unit.title}\" has been taken offline for review. {note}".strip(),
            "unhide": f"The review hold on \"{unit.title}\" was lifted. You can publish it again.",
            "mark_occupied": f"\"{unit.title}\" was marked as occupied and removed from search. {note}".strip(),
        }
        notify(recipient=landlord, event="listing.moderated", sms=action in ("reject", "hide"),
               dedupe_key=f"unit:{unit.pk}:moderation:{action}:{timezone.now().timestamp()}", title="Listing review update",
               message=messages[action], link="/landlord?tab=homes")
        _bust()
        return Response(_listing_row(unit))


class PropertyVerificationDecisionView(AdminView):
    """POST /admin/properties/<id>/verification/ {decision: verified|rejected|needs_review, note}"""

    @transaction.atomic
    def post(self, request, property_id):
        prop = get_object_or_404(Property.objects.select_for_update().select_related("landlord__user"), pk=property_id)
        decision = request.data.get("decision")
        note = str(request.data.get("note", ""))[:500]
        if decision not in ("verified", "rejected", "needs_review"):
            raise ValidationError({"decision": "Choose verified, rejected or needs_review."})
        if decision == "verified" and not prop.verification_payments.filter(purpose=Payment.Purpose.VERIFICATION_FEE, status=Payment.Status.SUCCESSFUL).exists():
            raise ValidationError("A property is verified only after its verification fee has been paid.")
        prop.verification_status = decision
        prop.save(update_fields=("verification_status", "updated_at"))
        audit(request, "property.verification_decided", prop, decision=decision, note=note[:200])
        notify(recipient=prop.landlord.user, event="verification.decided", dedupe_key=f"property:{prop.pk}:verification:{timezone.now().timestamp()}",
               title="Property verification update", link="/landlord?tab=homes",
               message={"verified": f"{prop.name} is now verified.",
                        "rejected": f"We could not verify {prop.name}: {note}",
                        "needs_review": f"{prop.name} needs another check: {note}"}[decision])
        _bust()
        return Response({"id": prop.pk, "verification_status": prop.verification_status})


class AdminPropertyListView(AdminView):
    def get(self, request):
        props = Property.objects.select_related("landlord__user").annotate(unit_count=Count("units"))
        if status := request.query_params.get("verification_status"):
            props = props.filter(verification_status=status)
        return self.paginate(props.order_by("updated_at", "id"), lambda p: {
            "id": p.pk, "name": p.name, "area": p.area, "city": p.city, "county": p.county,
            "verification_status": p.verification_status, "units": p.unit_count, "landlord": mask_phone(p.landlord.user.phone_number),
            "fee_paid": p.verification_payments.filter(purpose=Payment.Purpose.VERIFICATION_FEE, status=Payment.Status.SUCCESSFUL).exists(),
            "updated_at": p.updated_at,
        })


# ------------------------------------------------------------------ landlord verification

def _verification_row(v, detail=False):
    row = {"id": v.pk, "status": v.status, "legal_name": v.legal_name, "id_type": v.id_type, "id_last4": v.id_last4,
           "relationship": v.relationship, "agency_name": v.agency_name, "submitted_at": v.submitted_at,
           "reviewed_at": v.reviewed_at, "reviewer_note": v.reviewer_note, "landlord_id": v.landlord.user_id,
           "landlord": mask_phone(v.landlord.user.phone_number), "documents_purged": v.documents_purged_at is not None}
    if detail:
        row["landlord_phone"] = v.landlord.user.phone_number
        row["documents"] = [{"id": d.pk, "kind": d.kind, "label": d.get_kind_display(), "content_type": d.content_type,
                             "size": d.size, "available": bool(d.file),
                             "reused_elsewhere": VerificationDocument.objects.filter(sha256=d.sha256).exclude(verification__landlord=v.landlord).exists()}
                            for d in v.documents.all()]
        row["properties"] = list(v.landlord.properties.values("id", "name", "area", "city"))
    return row


class AdminVerificationListView(AdminView):
    def get(self, request):
        items = LandlordVerification.objects.select_related("landlord__user")
        status = request.query_params.get("status", "pending")
        if status != "all":
            items = items.filter(status=status)
        return self.paginate(items.order_by("submitted_at", "id"), _verification_row)


class AdminVerificationDetailView(AdminView):
    def get(self, request, verification_id):
        item = get_object_or_404(LandlordVerification.objects.select_related("landlord__user").prefetch_related("documents"), pk=verification_id)
        audit(request, "verification.viewed", item)
        return Response(_verification_row(item, detail=True))


class AdminVerificationDecideView(AdminView):
    def post(self, request, verification_id):
        get_object_or_404(LandlordVerification, pk=verification_id)
        item = verification_services.decide(verification_id, admin=request.user, decision=request.data.get("decision"),
                                            note=str(request.data.get("note", "")))
        return Response(_verification_row(item))


class AdminVerificationDocumentView(AdminView):
    """Stream one private document to an administrator. Every access is audited; nothing is cached."""

    def get(self, request, document_id):
        document = get_object_or_404(VerificationDocument.objects.select_related("verification"), pk=document_id)
        if not document.file:
            raise Conflict("This document was deleted after the retention period.", code="purged")
        audit(request, "verification.document_downloaded", document, verification_id=document.verification_id, kind=document.kind)
        response = FileResponse(document.file.open("rb"), content_type=document.content_type)
        response["Content-Disposition"] = f'inline; filename="verification-{document.verification_id}-{document.kind}"'
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox"
        return response


# ------------------------------------------------------------------ trust reports

def _report_row(r):
    return {"id": r.pk, "reason": r.reason, "detail": r.detail, "listing_id": r.listing_id,
            "listing": r.listing.title if r.listing_id else None, "reported_user_id": r.reported_user_id,
            "reported_user": mask_phone(r.reported_user.phone_number) if r.reported_user_id else None,
            "reporter": mask_phone(r.reporter.phone_number), "created_at": r.created_at,
            "resolved_at": r.resolved_at, "resolution": r.resolution,
            "same_listing_open": Report.objects.filter(listing_id=r.listing_id, resolved_at__isnull=True).count() if r.listing_id else 0}


class AdminReportListView(AdminView):
    def get(self, request):
        reports = Report.objects.select_related("listing", "reported_user", "reporter")
        if request.query_params.get("state", "open") == "open":
            reports = reports.filter(resolved_at__isnull=True)
        return self.paginate(reports.order_by("created_at", "id"), _report_row)


class AdminReportResolveView(AdminView):
    """POST /admin/reports/<id>/resolve/ {resolution: actioned|dismissed|duplicate, hide_listing, suspend_user, note}"""

    def post(self, request, report_id):
        report = get_object_or_404(Report.objects.select_related("reported_user"), pk=report_id)
        resolution = request.data.get("resolution")
        if resolution not in Report.Resolution.values:
            raise ValidationError({"resolution": "Choose actioned, dismissed or duplicate."})
        same = Report.objects.filter(pk=report.pk)
        if request.data.get("hide_listing"):
            trust_services.hide_reported_listings(same, request.user)
        if request.data.get("suspend_user") and report.reported_user_id:
            target = report.reported_user
            if target.is_staff or target.role == User.Role.ADMIN:
                raise ValidationError("Staff accounts cannot be suspended here.")
            trust_services.suspend_landlord(target, str(request.data.get("note", "Suspended after a reviewed report"))[:255], request.user)
        scope = Report.objects.filter(listing_id=report.listing_id) if report.listing_id and request.data.get("all_for_listing") else same
        count = trust_services.resolve_reports(scope, resolution, request.user)
        return Response({"resolved": count})


# ------------------------------------------------------------------ referral review

class AdminReferralReviewListView(AdminView):
    """Viewings that may have converted without a recorded fee: open flags and pending disputes."""

    def get(self, request):
        viewing_ids = set(ReferralFlag.objects.filter(status=ReferralFlag.Status.OPEN).values_list("viewing_id", flat=True))
        viewing_ids |= set(Dispute.objects.filter(status=Dispute.Status.PENDING).values_list("viewing_id", flat=True))
        viewings = (Viewing.objects.filter(pk__in=viewing_ids)
                    .select_related("request__unit__property__landlord__user", "request__tenant__user")
                    .prefetch_related("outcomes", "referral_flags").order_by("scheduled_at"))

        def row(v):
            tenant_id, landlord_id = v.request.tenant.user_id, v.request.unit.property.landlord.user_id
            return {
                "viewing_id": v.pk, "status": v.status, "scheduled_at": v.scheduled_at, "unit": v.request.unit.title,
                "unit_id": v.request.unit_id, "unit_available": v.request.unit.available, "monthly_rent": v.request.unit.monthly_rent,
                "tenant": mask_phone(v.request.tenant.user.phone_number), "landlord": mask_phone(v.request.unit.property.landlord.user.phone_number),
                "tenant_report": next((o.choice for o in v.outcomes.all() if o.reporter_id == tenant_id), None),
                "landlord_report": next((o.choice for o in v.outcomes.all() if o.reporter_id == landlord_id), None),
                "flags": [{"reason": f.reason, "label": f.get_reason_display(), "detail": f.detail, "created_at": f.created_at}
                          for f in v.referral_flags.all() if f.status == ReferralFlag.Status.OPEN],
                "dispute_open": Dispute.objects.filter(viewing=v, status=Dispute.Status.PENDING).exists(),
            }
        return self.paginate(viewings, row)


class AdminViewingRulingView(AdminView):
    """POST /admin/viewings/<id>/ruling/ {rented: bool, note} — decide whether the viewing led to a tenancy."""

    def post(self, request, viewing_id):
        viewing = get_object_or_404(Viewing, pk=viewing_id)
        rented = request.data.get("rented")
        if not isinstance(rented, bool):
            raise ValidationError({"rented": "Say whether the home was rented (true or false)."})
        note = str(request.data.get("note", "")).strip()
        if not note:
            raise ValidationError({"note": "Record the evidence for this decision."})
        fee = resolve_flag_or_dispute(viewing, admin=request.user, rented=rented, note=note)
        return Response({"viewing_id": viewing.pk, "rented": rented, "fee_id": fee.pk if fee else None})


# ------------------------------------------------------------------ payments

def _payment_row(p):
    return {"id": p.pk, "purpose": p.purpose, "status": p.status, "amount": p.amount, "currency": p.currency,
            "credits": p.credits, "phone": mask_phone(p.phone_number), "provider": p.provider,
            "provider_reference": p.provider_reference if not p.provider_reference.startswith("pending:") else "",
            "receipt": p.provider_receipt, "failure_reason": p.failure_reason, "created_at": p.created_at,
            "completed_at": p.completed_at, "refunded_at": p.refunded_at, "refund_reason": p.refund_reason}


def _payments(request):
    payments = Payment.objects.all()
    for field in ("status", "purpose"):
        if value := request.query_params.get(field):
            payments = payments.filter(**{field: value})
    if q := request.query_params.get("q", "").strip():
        payments = payments.filter(Q(provider_receipt__iexact=q) | Q(provider_reference__iexact=q) | Q(phone_number__icontains=q))
    if since := request.query_params.get("since"):
        payments = payments.filter(created_at__date__gte=since)
    return payments.order_by("-created_at", "-id")


class AdminPaymentListView(AdminView):
    def get(self, request):
        payments = _payments(request)
        response = self.paginate(payments, _payment_row)
        response.data["totals"] = {row["status"]: {"count": row["n"], "amount": row["total"] or 0}
                                   for row in payments.values("status").annotate(n=Count("id"), total=Sum("amount"))}
        return response


class AdminPaymentActionView(AdminView):
    """POST /admin/payments/<id>/refund/ {reason} | /reconcile/"""

    def post(self, request, payment_id, action):
        get_object_or_404(Payment, pk=payment_id)
        if action == "refund":
            reason = str(request.data.get("reason", "")).strip()
            if not reason:
                raise ValidationError({"reason": "Record why and how the money was returned (e.g. M-Pesa reversal reference)."})
            return Response(_payment_row(payment_services.record_refund(payment_id, admin=request.user, reason=reason)))
        if action == "reconcile":
            payment = payment_services.reconcile_payment(payment_id)
            audit(request, "payment.reconcile_requested", payment, status=payment.status)
            return Response(_payment_row(payment))
        raise ValidationError("Unknown action.")


# ------------------------------------------------------------------ pricing

class PackageAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = ViewingPackage
        fields = ("id", "country", "name", "description", "credits", "price", "currency", "is_active", "sort_order", "updated_at")
        # DRF cannot build a validator for the conditional unique constraint on partial updates; checked below.
        validators = []

    def validate(self, attrs):
        country = attrs.get("country", getattr(self.instance, "country", "KE"))
        credits = attrs.get("credits", getattr(self.instance, "credits", None))
        active = attrs.get("is_active", getattr(self.instance, "is_active", True))
        clash = ViewingPackage.objects.filter(country=country, credits=credits, is_active=True)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if active and clash.exists():
            raise serializers.ValidationError("An active package with that many credits already exists for this country.")
        return attrs


class FeeRuleAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralFeeRule
        fields = ("id", "country", "min_rent", "max_rent", "fee_type", "amount", "percent", "currency", "is_active", "updated_at")

    def validate(self, attrs):
        low = attrs.get("min_rent", getattr(self.instance, "min_rent", 0))
        high = attrs.get("max_rent", getattr(self.instance, "max_rent", None))
        if high is not None and high < low:
            raise serializers.ValidationError("max_rent must be at least min_rent.")
        return attrs


class ServicePriceAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicePrice
        fields = ("id", "country", "code", "amount", "currency", "is_active", "updated_at")


def pricing_views(model, serializer_class, label):
    class ListCreate(AdminView):
        def get(self, request):
            return Response(serializer_class(model.objects.all(), many=True).data)

        def post(self, request):
            serializer = serializer_class(data=request.data)
            serializer.is_valid(raise_exception=True)
            obj = serializer.save()
            audit(request, f"pricing.{label}.created", obj, **{k: str(v) for k, v in serializer.validated_data.items()})
            return Response(serializer_class(obj).data, status=201)

    class Detail(AdminView):
        def patch(self, request, pk):
            obj = get_object_or_404(model, pk=pk)
            before = serializer_class(obj).data
            serializer = serializer_class(obj, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            obj = serializer.save()
            after = serializer_class(obj).data
            audit(request, f"pricing.{label}.updated", obj,
                  changes={k: [str(before[k]), str(after[k])] for k in after if k != "updated_at" and before.get(k) != after[k]})
            return Response(after)

    ListCreate.__name__ = f"Admin{label.title()}ListCreateView"
    Detail.__name__ = f"Admin{label.title()}DetailView"
    return ListCreate, Detail


PackageListCreateView, PackageDetailView = pricing_views(ViewingPackage, PackageAdminSerializer, "package")
FeeRuleListCreateView, FeeRuleDetailView = pricing_views(ReferralFeeRule, FeeRuleAdminSerializer, "fee_rule")
ServicePriceListCreateView, ServicePriceDetailView = pricing_views(ServicePrice, ServicePriceAdminSerializer, "service_price")


# ------------------------------------------------------------------ users

class AdminUserActionView(AdminView):
    """POST /admin/users/<id>/suspend/ {reason} | /reinstate/"""

    def post(self, request, user_id, action):
        target = get_object_or_404(User, pk=user_id)
        if target.is_staff or target.role == User.Role.ADMIN:
            raise ValidationError("Administrator accounts are managed in Django admin by a superuser.")
        if action == "suspend":
            reason = str(request.data.get("reason", "")).strip()
            if not reason:
                raise ValidationError({"reason": "Record why the account is suspended."})
            trust_services.suspend_landlord(target, reason, request.user)
        elif action == "reinstate":
            trust_services.lift_suspension(target, request.user)
        else:
            raise ValidationError("Unknown action.")
        return Response({"id": target.pk, "active": User.objects.get(pk=target.pk).is_active})


class AdminUserDetailView(AdminView):
    def get(self, request, user_id):
        target = get_object_or_404(User, pk=user_id)
        audit(request, "admin.user_viewed", target)
        data = {"id": target.pk, "role": target.role, "phone": target.phone_number, "name": f"{target.first_name} {target.last_name}".strip(),
                "email": target.email, "active": target.is_active, "verified_phone": target.phone_verified, "joined": target.created_at,
                "restrictions": list(target.restrictions.values("reason", "created_at", "expires_at"))}
        if target.role == User.Role.LANDLORD:
            data["listings"] = Unit.objects.filter(property__landlord__user=target).count()
            data["landlord_verified"] = getattr(getattr(target, "landlord_profile", None), "verification_tier", "basic") != "basic"
            data["fees"] = {row["status"]: row["n"] for row in ReferralFee.objects.filter(attribution__landlord__user=target).values("status").annotate(n=Count("id"))}
        if target.role == User.Role.TENANT:
            data["viewing_requests"] = ViewingRequest.objects.filter(tenant__user=target).count()
            data["payments"] = Payment.objects.filter(tenant_user=target, status=Payment.Status.SUCCESSFUL).count()
        data["reports_received"] = Report.objects.filter(reported_user=target).count()
        return Response(data)


# ------------------------------------------------------------------ audit log

class AdminAuditLogView(AdminView):
    def get(self, request):
        entries = AuditLog.objects.select_related("actor")
        for field in ("action", "object_type", "object_id"):
            if value := request.query_params.get(field):
                entries = entries.filter(**({f"{field}__startswith": value} if field == "action" else {field: value}))
        if actor := request.query_params.get("actor"):
            entries = entries.filter(actor_ref=actor)
        return self.paginate(entries.order_by("-id"), lambda e: {
            "id": e.pk, "action": e.action, "object_type": e.object_type, "object_id": e.object_id,
            "actor": (f"{e.actor.role}:{mask_phone(e.actor.phone_number)}" if e.actor else ("deleted user" if e.actor_ref else "system")),
            "metadata": e.metadata, "created_at": e.created_at, "entry_hash": e.entry_hash[:12],
        })


class AdminAuditVerifyView(AdminView):
    def get(self, request):
        checked, broken = verify_audit_chain()
        audit(request, "audit.chain_verified", intact=broken is None, checked=checked)
        return Response({"intact": broken is None, "checked": checked, "first_broken_id": broken})


# ------------------------------------------------------------------ market reports

GROUPS = {"county": ("county",), "town": ("county", "city"), "estate": ("county", "city", "area")}


def area_report(group="estate", days=90):
    keys = GROUPS.get(group, GROUPS["estate"])
    since = timezone.now() - timedelta(days=days)
    public_ids = public_units().values("pk")
    supply = {tuple(r[f"property__{k}"] for k in keys): r for r in Unit.objects.filter(property__is_active=True)
              .values(*[f"property__{k}" for k in keys])
              .annotate(listings=Count("id", filter=Q(pk__in=public_ids)), units=Count("id"),
                        occupied=Count("id", filter=Q(available=False)), avg_rent=Avg("monthly_rent", filter=Q(pk__in=public_ids)))}
    demand = {tuple(r[f"unit__property__{k}"] for k in keys): r for r in ViewingRequest.objects.filter(created_at__gte=since)
              .values(*[f"unit__property__{k}" for k in keys])
              .annotate(requests=Count("id"), tenants=Count("tenant", distinct=True),
                        completed=Count("id", filter=Q(viewing__completed_at__isnull=False)),
                        rented=Count("id", filter=Q(viewing__status=Viewing.Status.RENTED)))}
    views = {tuple(r[f"unit__property__{k}"] for k in keys): r["views"] for r in UnitDailyStat.objects.filter(date__gte=since.date())
             .values(*[f"unit__property__{k}" for k in keys]).annotate(views=Sum("views"))}
    rows = []
    for key in set(supply) | set(demand) | set(views):
        s, d = supply.get(key, {}), demand.get(key, {})
        listings = s.get("listings") or 0
        requests = d.get("requests") or 0
        rows.append({
            **dict(zip(("county", "town", "estate")[:len(keys)], key)),
            "active_listings": listings, "total_units": s.get("units") or 0, "occupied_units": s.get("occupied") or 0,
            "avg_rent": round(s["avg_rent"]) if s.get("avg_rent") else None, "listing_views": views.get(key, 0),
            "viewing_requests": requests, "tenants_searching": d.get("tenants") or 0,
            "completed_viewings": d.get("completed") or 0, "rentals": d.get("rented") or 0,
            "demand_per_listing": round(requests / listings, 2) if listings else (float(requests) if requests else 0.0),
            # High demand and low supply: worth recruiting landlords here.
            "undersupplied": requests >= 3 and (listings == 0 or requests / listings >= 3),
        })
    rows.sort(key=lambda r: (-r["demand_per_listing"], -r["viewing_requests"]))
    return rows


class AdminAreaReportView(AdminView):
    def get(self, request):
        group = request.query_params.get("group", "estate")
        days = min(max(int(request.query_params.get("days", 90) or 90), 7), 365)
        return Response({"group": group, "days": days, "rows": area_report(group, days)})


class AdminTrendView(AdminView):
    """Daily counts for the last N days: sign-ups, requests, approvals, rentals, revenue."""

    def get(self, request):
        days = min(max(int(request.query_params.get("days", 30) or 30), 7), 180)
        since = timezone.now() - timedelta(days=days)

        def daily(queryset, field="created_at", value=Count("id")):
            return {r["day"].isoformat(): r["v"] for r in queryset.filter(**{f"{field}__gte": since})
                    .annotate(day=TruncDate(field)).values("day").annotate(v=value)}
        series = {
            "signups": daily(User.objects.all()),
            "viewing_requests": daily(ViewingRequest.objects.all()),
            "approved": daily(ViewingRequest.objects.filter(responded_at__isnull=False, status__in=("approved",)), "responded_at"),
            "rentals": daily(ReferralFee.objects.all()),
            "revenue": daily(Payment.objects.filter(status=Payment.Status.SUCCESSFUL), "completed_at", Sum("amount")),
        }
        dates = [(timezone.localdate() - timedelta(days=offset)).isoformat() for offset in range(days - 1, -1, -1)]
        return Response({"dates": dates, "series": {name: [values.get(d, 0) or 0 for d in dates] for name, values in series.items()}})


# ------------------------------------------------------------------ CSV exports

def _csv_response(filename, header, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-store"
    writer = csv.writer(response)
    writer.writerow(header)
    for row in rows:
        # Neutralise spreadsheet formula injection from user-entered text.
        writer.writerow([f"'{cell}" if isinstance(cell, str) and cell[:1] in ("=", "+", "-", "@") else cell for cell in row])
    return response


class AdminExportView(AdminView):
    """GET /admin/exports/<payments|areas|viewings|listings>.csv — business reports, phone numbers masked."""

    def get(self, request, name):
        audit(request, "admin.export", report=name, params=dict(request.query_params))
        today = timezone.localdate().isoformat()
        if name == "payments":
            rows = ((p.pk, p.created_at.isoformat(), p.purpose, p.status, p.amount, p.currency, p.credits or "", p.provider_receipt or "",
                     p.failure_reason, mask_phone(p.phone_number), p.completed_at.isoformat() if p.completed_at else "",
                     p.refunded_at.isoformat() if p.refunded_at else "") for p in _payments(request).iterator())
            return _csv_response(f"payments-{today}.csv", ["id", "created_at", "purpose", "status", "amount", "currency", "credits",
                                                          "receipt", "failure_reason", "phone", "completed_at", "refunded_at"], rows)
        if name == "areas":
            group = request.query_params.get("group", "estate")
            report = area_report(group, int(request.query_params.get("days", 90) or 90))
            header = list(report[0].keys()) if report else ["county", "active_listings", "viewing_requests"]
            return _csv_response(f"areas-{group}-{today}.csv", header, ([r.get(h) for h in header] for r in report))
        if name == "viewings":
            items = ViewingRequest.objects.select_related("unit__property", "viewing").order_by("-created_at")
            rows = ((i.pk, i.created_at.isoformat(), i.status, i.unit.property.county, i.unit.property.city, i.unit.property.area,
                     i.unit.monthly_rent, i.responded_at.isoformat() if i.responded_at else "",
                     getattr(getattr(i, "viewing", None), "status", ""), i.cancelled_by) for i in items.iterator())
            return _csv_response(f"viewings-{today}.csv", ["id", "requested_at", "status", "county", "town", "estate", "rent",
                                                          "responded_at", "viewing_status", "cancelled_by"], rows)
        if name == "listings":
            units = Unit.objects.select_related("property").order_by("-created_at")
            rows = ((u.pk, u.created_at.isoformat(), u.property.county, u.property.city, u.property.area, u.unit_type, u.bedrooms,
                     u.monthly_rent, u.available, u.is_published, u.moderation_status, u.property.verification_status) for u in units.iterator())
            return _csv_response(f"listings-{today}.csv", ["id", "created_at", "county", "town", "estate", "type", "bedrooms", "rent",
                                                          "available", "published", "moderation", "verification"], rows)
        raise ValidationError("Unknown export.")
