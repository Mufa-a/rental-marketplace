import csv
import io
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import LandlordProfile, TenantProfile, User
from apps.core.models import AuditLog
from apps.notifications.models import Notification
from apps.payments.models import Payment, ViewingPackage
from apps.properties.models import Property, Unit
from apps.trust.models import Report
from apps.verification.models import LandlordVerification, VerificationDocument

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200
PDF = b"%PDF-1.4\n" + b"0" * 200

ADMIN_GET_ENDPOINTS = [
    "/api/v1/admin/overview/", "/api/v1/admin/users/", "/api/v1/admin/viewing-requests/", "/api/v1/admin/listings/",
    "/api/v1/admin/properties/", "/api/v1/admin/landlord-verifications/", "/api/v1/admin/reports/",
    "/api/v1/admin/referral-reviews/", "/api/v1/admin/payments/", "/api/v1/admin/pricing/packages/",
    "/api/v1/admin/pricing/fee-rules/", "/api/v1/admin/pricing/service-prices/", "/api/v1/admin/audit-logs/",
    "/api/v1/admin/audit-logs/verify/", "/api/v1/admin/market/areas/", "/api/v1/admin/market/trends/",
    "/api/v1/admin/exports/payments.csv", "/api/v1/admin/exports/areas.csv",
]


def make_admin(phone="+254700001000"):
    return User.objects.create_superuser(phone_number=phone, password="x-secure-password-123")


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def landlord_with_unit(phone="+254722001000", **unit_fields):
    user = User.objects.create_user(phone_number=phone, role=User.Role.LANDLORD)
    profile = LandlordProfile.objects.create(user=user)
    prop = Property.objects.create(landlord=profile, name="Court", address_line="1 Road", area="Kilimani", city="Nairobi", county="Nairobi")
    unit = Unit.objects.create(property=prop, unit_number="1", title="Bright studio", unit_type="studio", monthly_rent=15000,
                               is_published=True, **unit_fields)
    return user, unit


@pytest.mark.django_db
@pytest.mark.parametrize("path", ADMIN_GET_ENDPOINTS)
def test_every_admin_endpoint_is_closed_to_everyone_but_platform_admins(path):
    assert APIClient().get(path).status_code == 401
    tenant = User.objects.create_user(phone_number="+254711009001", role=User.Role.TENANT)
    landlord = User.objects.create_user(phone_number="+254711009002", role=User.Role.LANDLORD)
    role_only = User.objects.create_user(phone_number="+254711009003", role=User.Role.ADMIN)  # not staff
    inactive = make_admin("+254711009004")
    inactive.is_active = False
    inactive.save()
    for user in (tenant, landlord, role_only):
        assert client_for(user).get(path).status_code == 403, user.role
    assert client_for(inactive).get(path).status_code in (401, 403)
    assert client_for(make_admin()).get(path).status_code == 200


@pytest.mark.django_db
def test_admin_write_endpoints_reject_non_admins():
    landlord, unit = landlord_with_unit()
    client = client_for(landlord)
    assert client.post(f"/api/v1/admin/listings/{unit.pk}/moderate/", {"action": "approve"}, format="json").status_code == 403
    assert client.post("/api/v1/admin/pricing/packages/", {"name": "Free", "credits": 99, "price": 1}, format="json").status_code == 403
    assert client.patch(f"/api/v1/admin/pricing/packages/{ViewingPackage.objects.first().pk}/", {"price": 1}, format="json").status_code == 403
    assert ViewingPackage.objects.filter(price=1).count() == 0


@pytest.mark.django_db
class TestListingModeration:
    def test_request_changes_then_resubmit_then_approve(self):
        landlord, unit = landlord_with_unit(moderation_status="pending_review")
        admin = client_for(make_admin())
        assert admin.get("/api/v1/admin/listings/?moderation_status=pending_review").data["count"] == 1
        assert admin.post(f"/api/v1/admin/listings/{unit.pk}/moderate/", {"action": "request_changes"}, format="json").status_code == 400
        assert admin.post(f"/api/v1/admin/listings/{unit.pk}/moderate/", {"action": "request_changes", "note": "Add real photos"}, format="json").status_code == 200
        assert landlord.notifications.filter(event="listing.moderated", channel="in_app").exists()

        client_for(landlord).patch(f"/api/v1/properties/units/{unit.pk}/", {"description": "Now with photos"}, format="json")
        unit.refresh_from_db()
        assert unit.moderation_status == "pending_review"
        admin.post(f"/api/v1/admin/listings/{unit.pk}/moderate/", {"action": "approve"}, format="json")
        assert APIClient().get("/api/v1/properties/search/").data["count"] == 1
        assert AuditLog.objects.filter(action="unit.moderation.approve").exists()

    def test_mark_occupied_removes_from_search(self):
        _, unit = landlord_with_unit()
        client_for(make_admin()).post(f"/api/v1/admin/listings/{unit.pk}/moderate/", {"action": "mark_occupied"}, format="json")
        unit.refresh_from_db()
        assert not unit.available and APIClient().get("/api/v1/properties/search/").data["count"] == 0

    def test_property_is_verified_only_after_the_fee_is_paid(self):
        _, unit = landlord_with_unit()
        admin = client_for(make_admin())
        url = f"/api/v1/admin/properties/{unit.property_id}/verification/"
        assert admin.post(url, {"decision": "verified"}, format="json").status_code == 400
        Payment.objects.create(purpose="verification_fee", property=unit.property, amount=2000, phone_number="+254722001000",
                               provider_reference="ws_1", idempotency_key="v1", status="successful")
        assert admin.post(url, {"decision": "verified"}, format="json").status_code == 200
        assert APIClient().get("/api/v1/properties/search/?verified_only=true").data["count"] == 1


@pytest.mark.django_db
class TestLandlordVerification:
    def _submit(self, landlord, **extra):
        data = {"legal_name": "Wanjiru Kamau", "id_type": "national_id", "id_number": "12345678", "relationship": "owner",
                "id_front": SimpleUploadedFile("id.jpg", JPEG, content_type="image/jpeg"), **extra}
        return client_for(landlord).post("/api/v1/verification/landlord/", data, format="multipart")

    def test_submission_stores_only_the_last_four_id_digits_and_private_files(self, settings):
        landlord, _ = landlord_with_unit()
        response = self._submit(landlord, ownership_proof=SimpleUploadedFile("deed.pdf", PDF, content_type="application/pdf"))
        assert response.status_code == 201, response.data
        verification = LandlordVerification.objects.get()
        assert verification.id_last4 == "5678"
        assert "12345678" not in str(LandlordVerification.objects.values().get())
        document = verification.documents.get(kind="id_front")
        assert document.content_type == "image/jpeg" and "id.jpg" not in document.file.name
        assert document.file.path.startswith(settings.PRIVATE_MEDIA_ROOT)  # private root, never under a served path
        # A second submission while one is pending is refused.
        assert self._submit(landlord).status_code == 409

    def test_files_are_checked_by_content_not_by_name(self):
        landlord, _ = landlord_with_unit()
        fake = SimpleUploadedFile("id.jpg", b"<html><script>alert(1)</script>", content_type="image/jpeg")
        response = client_for(landlord).post("/api/v1/verification/landlord/", {
            "legal_name": "X Y", "id_type": "national_id", "id_number": "12345678", "relationship": "owner", "id_front": fake}, format="multipart")
        assert response.status_code == 400 and LandlordVerification.objects.count() == 0

    def test_agents_must_provide_an_authority_letter(self):
        landlord, _ = landlord_with_unit()
        assert self._submit(landlord, relationship="agent").status_code == 400

    def test_only_admins_read_documents_and_every_read_is_audited(self):
        landlord, _ = landlord_with_unit()
        self._submit(landlord)
        document = VerificationDocument.objects.get()
        url = f"/api/v1/admin/verification-documents/{document.pk}/"
        assert client_for(landlord).get(url).status_code == 403
        response = client_for(make_admin()).get(url)
        assert response.status_code == 200 and b"".join(response.streaming_content).startswith(b"\xff\xd8\xff")
        assert response["Cache-Control"] == "no-store"
        assert AuditLog.objects.filter(action="verification.document_downloaded", object_id=str(document.pk)).exists()

    def test_decision_sets_the_public_badge_and_documents_are_purged_later(self, settings):
        from apps.verification.services import purge_expired_documents
        landlord, unit = landlord_with_unit()
        self._submit(landlord)
        verification = LandlordVerification.objects.get()
        admin = client_for(make_admin())
        url = f"/api/v1/admin/landlord-verifications/{verification.pk}/decide/"
        assert admin.post(url, {"decision": "rejected"}, format="json").status_code == 400  # a reason is required
        assert admin.post(url, {"decision": "verified"}, format="json").status_code == 200
        listing = APIClient().get("/api/v1/properties/search/").data["results"][0]
        assert listing["property"]["landlord_verified"] is True
        assert landlord.notifications.filter(event="verification.decided").exists()

        LandlordVerification.objects.filter(pk=verification.pk).update(reviewed_at=timezone.now() - timedelta(days=settings.VERIFICATION_DOCUMENT_RETENTION_DAYS + 1))
        assert purge_expired_documents() == 1
        document = VerificationDocument.objects.get()
        assert not document.file and document.sha256
        assert admin.get(f"/api/v1/admin/verification-documents/{document.pk}/").status_code == 409


@pytest.mark.django_db
def test_report_resolution_can_hide_the_listing_and_suspend_the_landlord():
    landlord, unit = landlord_with_unit()
    tenant = User.objects.create_user(phone_number="+254711002000", role=User.Role.TENANT)
    report = Report.objects.create(reporter=tenant, reported_user=landlord, listing=unit, reason="fake_photos", detail="Stock photos")
    admin = client_for(make_admin())
    assert admin.get("/api/v1/admin/reports/").data["count"] == 1
    response = admin.post(f"/api/v1/admin/reports/{report.pk}/resolve/",
                          {"resolution": "actioned", "hide_listing": True, "suspend_user": True, "note": "Scam"}, format="json")
    assert response.status_code == 200
    landlord.refresh_from_db(); unit.refresh_from_db(); report.refresh_from_db()
    assert not landlord.is_active and unit.moderation_hold and report.resolution == "actioned"


@pytest.mark.django_db
def test_report_accepts_the_new_fraud_reasons():
    _, unit = landlord_with_unit()
    tenant = User.objects.create_user(phone_number="+254711002001", role=User.Role.TENANT)
    for reason in ("fake_photos", "property_unavailable", "misleading_price"):
        Report.objects.filter(reporter=tenant).update(resolved_at=timezone.now())
        response = client_for(tenant).post("/api/v1/trust/reports/", {"listing_id": unit.pk, "reason": reason}, format="json")
        assert response.status_code == 201, response.data


@pytest.mark.django_db
def test_pricing_changes_take_effect_immediately_and_are_audited():
    admin = client_for(make_admin())
    package = ViewingPackage.objects.get(country="KE", credits=2)
    response = admin.patch(f"/api/v1/admin/pricing/packages/{package.pk}/", {"price": 90}, format="json")
    assert response.status_code == 200
    prices = {p["credits"]: p["price"] for p in APIClient().get("/api/v1/payments/prices/").data["viewing_packages"]}
    assert prices[2] == 90
    entry = AuditLog.objects.get(action="pricing.package.updated")
    assert entry.metadata["changes"]["price"] == ["100", "90"]
    assert admin.post("/api/v1/admin/pricing/fee-rules/", {"country": "UG", "min_rent": 100, "max_rent": 50, "amount": 1}, format="json").status_code == 400


@pytest.mark.django_db
def test_admin_records_refund_through_the_api():
    tenant = User.objects.create_user(phone_number="+254711003000", role=User.Role.TENANT)
    payment = Payment.objects.create(purpose="viewing_credits", tenant_user=tenant, credits=2, amount=100, phone_number=tenant.phone_number,
                                     provider_reference="ws_r", idempotency_key="r", status="successful")
    admin = client_for(make_admin())
    assert admin.post(f"/api/v1/admin/payments/{payment.pk}/refund/", {}, format="json").status_code == 400
    assert admin.post(f"/api/v1/admin/payments/{payment.pk}/refund/", {"reason": "Reversal QKX1"}, format="json").data["status"] == "refunded"
    assert admin.get("/api/v1/admin/payments/?status=refunded").data["count"] == 1


@pytest.mark.django_db
def test_audit_chain_verification_endpoint():
    admin = client_for(make_admin())
    AuditLog.objects.create(action="test.one", object_type="t", object_id="1")
    assert admin.get("/api/v1/admin/audit-logs/verify/").data["intact"] is True
    assert admin.get("/api/v1/admin/audit-logs/?action=test.").data["count"] == 1


@pytest.mark.django_db
def test_area_report_flags_undersupplied_estates_and_exports_safe_csv():
    from apps.viewings.models import ViewingRequest
    landlord, unit = landlord_with_unit()
    Property.objects.filter(pk=unit.property_id).update(area="=HYPERLINK(1)")
    for n in range(4):
        tenant = User.objects.create_user(phone_number=f"+25471100400{n}", role=User.Role.TENANT)
        ViewingRequest.objects.create(tenant=TenantProfile.objects.create(user=tenant), unit=unit, status="rejected")
    admin = client_for(make_admin())
    rows = admin.get("/api/v1/admin/market/areas/?group=estate").data["rows"]
    assert rows[0]["viewing_requests"] == 4 and rows[0]["undersupplied"] is True
    county = admin.get("/api/v1/admin/market/areas/?group=county").data["rows"][0]
    assert set(county) >= {"county", "active_listings", "demand_per_listing"} and "estate" not in county

    response = admin.get("/api/v1/admin/exports/areas.csv")
    body = b"".join(response.streaming_content if response.streaming else [response.content]).decode()
    cells = [cell for row in csv.reader(io.StringIO(body)) for cell in row]
    assert "'=HYPERLINK(1)" in cells and "=HYPERLINK(1)" not in cells
    assert AuditLog.objects.filter(action="admin.export").exists()


@pytest.mark.django_db
def test_notification_inbox_is_private_and_can_be_marked_read():
    from apps.notifications.services import notify
    alice = User.objects.create_user(phone_number="+254711005000", role=User.Role.TENANT)
    bob = User.objects.create_user(phone_number="+254711005001", role=User.Role.TENANT)
    notify(recipient=alice, event="viewing.approved", dedupe_key="a1", title="Approved", message="Your viewing is approved")
    notify(recipient=alice, event="listing.unavailable", dedupe_key="a2", message="Gone", sms=False)
    assert Notification.objects.filter(recipient=alice, channel="sms").count() == 1
    inbox = client_for(alice).get("/api/v1/notifications/").data
    assert inbox["unread"] == 2 and len(inbox["results"]) == 2
    assert client_for(bob).get("/api/v1/notifications/").data["results"] == []
    other_id = inbox["results"][0]["id"]
    client_for(bob).post("/api/v1/notifications/read/", {"ids": [other_id]}, format="json")
    assert client_for(alice).get("/api/v1/notifications/unread-count/").data["unread"] == 2
    client_for(alice).post("/api/v1/notifications/read/", {}, format="json")
    assert client_for(alice).get("/api/v1/notifications/unread-count/").data["unread"] == 0


@pytest.mark.django_db
def test_sms_delivery_gives_up_after_bounded_retries(settings, monkeypatch):
    import sys
    import types
    from apps.notifications.services import MAX_DELIVERY_ATTEMPTS, deliver_pending, notify
    settings.AFRICASTALKING_API_KEY = "key"
    fake = types.SimpleNamespace(initialize=lambda *a: None, SMS=types.SimpleNamespace(send=lambda *a: {"SMSMessageData": {"Recipients": [{"status": "Failed"}]}}))
    monkeypatch.setitem(sys.modules, "africastalking", fake)
    user = User.objects.create_user(phone_number="+254711006000", role=User.Role.TENANT)
    notify(recipient=user, event="viewing.approved", dedupe_key="x", message="hi")
    for _ in range(MAX_DELIVERY_ATTEMPTS + 2):
        deliver_pending()
    sms = Notification.objects.get(channel="sms")
    assert sms.status == "abandoned" and sms.attempt_count == MAX_DELIVERY_ATTEMPTS
