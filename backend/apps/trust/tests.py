import pytest
from rest_framework.test import APIClient

from apps.accounts.models import LandlordProfile, User
from apps.properties.models import Property, Unit
from apps.trust.models import AccountRestriction, Report
from apps.trust import services
from django.core.cache import cache


def _unit():
    owner = User.objects.create_user(username="ll", phone_number="+254700000051", role="landlord")
    prop = Property.objects.create(landlord=LandlordProfile.objects.create(user=owner), name="P", address_line="1", area="A", city="C", county="K")
    return owner, Unit.objects.create(property=prop, unit_number="1", title="T", unit_type="studio", monthly_rent=10000, is_published=True)


@pytest.mark.django_db
class TestReports:
    def test_signed_in_user_can_report_a_listing(self):
        owner, unit = _unit()
        reporter = User.objects.create_user(username="rp", phone_number="+254700000052", role="tenant")
        client = APIClient()
        client.force_authenticate(reporter)
        response = client.post("/api/v1/trust/reports/", {"listing_id": unit.id, "reason": "fraudulent_listing", "detail": "Asked me to pay a deposit first"}, format="json")
        assert response.status_code == 201
        report = Report.objects.get()
        assert report.reporter_id == reporter.id and report.reported_user_id == owner.id
        assert "reporter" not in response.data

    def test_anonymous_cannot_report_and_bad_reasons_are_rejected(self):
        _, unit = _unit()
        assert APIClient().post("/api/v1/trust/reports/", {"listing_id": unit.id, "reason": "other"}, format="json").status_code == 401
        user = User.objects.create_user(username="rp2", phone_number="+254700000053", role="tenant")
        client = APIClient()
        client.force_authenticate(user)
        assert client.post("/api/v1/trust/reports/", {"listing_id": unit.id, "reason": "made-up"}, format="json").status_code == 400


def _tenant(n):
    return User.objects.create_user(username=f"t{n}", phone_number=f"+2547000001{n:02d}", role="tenant")


def _report(client_user, unit, reason="fraudulent_listing"):
    client = APIClient()
    client.force_authenticate(client_user)
    return client.post("/api/v1/trust/reports/", {"listing_id": unit.id, "reason": reason}, format="json")


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    cache.clear()


@pytest.mark.django_db
class TestReportAbuseControls:
    def test_same_person_cannot_file_two_open_reports_on_one_listing(self):
        _, unit = _unit()
        reporter = _tenant(1)
        assert _report(reporter, unit).status_code == 201
        second = _report(reporter, unit)
        assert second.status_code == 409 and second.data["error"]["code"] == "already_reported"
        assert Report.objects.count() == 1

    def test_can_report_again_after_the_first_is_resolved(self):
        owner, unit = _unit()
        reporter = _tenant(1)
        _report(reporter, unit)
        admin = User.objects.create_user(username="ad", phone_number="+254700000199", role="admin")
        services.resolve_reports(Report.objects.all(), Report.Resolution.DISMISSED, admin)
        assert _report(reporter, unit).status_code == 201

    def test_landlord_cannot_report_their_own_listing(self):
        owner, unit = _unit()
        response = _report(owner, unit)
        assert response.status_code == 400 and response.data["error"]["code"] == "own_listing"

    def test_listing_is_hidden_once_threshold_of_different_reporters_is_reached(self, settings):
        settings.REPORT_AUTO_HIDE_THRESHOLD = 3
        _, unit = _unit()
        for n in (1, 2):
            _report(_tenant(n), unit)
        unit.refresh_from_db()
        assert unit.is_published and not unit.moderation_hold
        _report(_tenant(3), unit)
        unit.refresh_from_db()
        assert not unit.is_published and unit.moderation_hold

    def test_non_serious_reasons_do_not_count_toward_auto_hide(self, settings):
        settings.REPORT_AUTO_HIDE_THRESHOLD = 2
        _, unit = _unit()
        for n in (1, 2, 3):
            _report(_tenant(n), unit, reason="other")
        unit.refresh_from_db()
        assert unit.is_published

    def test_landlord_cannot_republish_a_held_listing_but_admin_can(self, settings):
        settings.REPORT_AUTO_HIDE_THRESHOLD = 1
        owner, unit = _unit()
        _report(_tenant(1), unit)
        landlord = APIClient()
        landlord.force_authenticate(owner)
        response = landlord.patch(f"/api/v1/properties/units/{unit.id}/", {"is_published": True}, format="json")
        assert response.status_code == 403 and response.data["error"]["code"] == "under_review"
        unit.refresh_from_db()
        assert not unit.is_published
        # moderation_hold itself is not writable by the landlord
        landlord.patch(f"/api/v1/properties/units/{unit.id}/", {"moderation_hold": False}, format="json")
        unit.refresh_from_db()
        assert unit.moderation_hold
        admin = APIClient()
        admin.force_authenticate(User.objects.create_user(username="ad", phone_number="+254700000199", role="admin"))
        assert admin.patch(f"/api/v1/properties/units/{unit.id}/", {"is_published": True}, format="json").status_code == 200


@pytest.mark.django_db
class TestModerationActions:
    def test_suspend_landlord_deactivates_account_and_hides_everything(self):
        owner, unit = _unit()
        admin = User.objects.create_user(username="ad", phone_number="+254700000199", role="admin")
        services.suspend_landlord(owner, "Took deposits for a house that does not exist", admin)
        owner.refresh_from_db(); unit.refresh_from_db()
        assert not owner.is_active and not unit.is_published and unit.moderation_hold
        assert AccountRestriction.objects.filter(user=owner).exists()

    def test_lift_suspension_reactivates_but_does_not_republish(self):
        owner, unit = _unit()
        admin = User.objects.create_user(username="ad", phone_number="+254700000199", role="admin")
        services.suspend_landlord(owner, "test", admin)
        services.lift_suspension(owner, admin)
        owner.refresh_from_db(); unit.refresh_from_db()
        assert owner.is_active and not unit.moderation_hold and not unit.is_published
        restriction = AccountRestriction.objects.get(user=owner)
        assert restriction.expires_at is not None

    def test_hide_and_resolve_marks_reports_actioned_with_the_admin_recorded(self):
        _, unit = _unit()
        _report(_tenant(1), unit)
        admin = User.objects.create_user(username="ad", phone_number="+254700000199", role="admin")
        reports = Report.objects.all()
        services.hide_reported_listings(reports, admin)
        services.resolve_reports(reports, Report.Resolution.ACTIONED, admin)
        report = Report.objects.get()
        unit.refresh_from_db()
        assert not unit.is_published and report.resolution == "actioned" and report.resolved_by_id == admin.id
