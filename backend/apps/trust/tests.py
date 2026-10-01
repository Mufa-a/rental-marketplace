import pytest
from rest_framework.test import APIClient

from apps.accounts.models import LandlordProfile, User
from apps.properties.models import Property, Unit
from apps.trust.models import Report


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
