import pytest
from rest_framework.test import APIClient

from apps.accounts.models import LandlordProfile, TenantProfile, User
from apps.properties.models import Amenity, Property, Unit


def landlord(phone="+254700000001"):
    user = User.objects.create_user(username=phone, phone_number=phone, role=User.Role.LANDLORD)
    LandlordProfile.objects.create(user=user)
    return user


def property_payload():
    return {"name": "Green Apartments", "address_line": "12 Parklands Road", "area": "Westlands", "city": "Nairobi", "county": "Nairobi", "latitude": -1.2676, "longitude": 36.8108}


@pytest.mark.django_db
class TestListingsAPI:
    def test_landlord_can_create_property_and_unit(self):
        user = landlord()
        amenity = Amenity.objects.create(name="Borehole")
        client = APIClient()
        client.force_authenticate(user)

        property_response = client.post("/api/v1/properties/mine/", property_payload(), format="json")
        assert property_response.status_code == 201
        assert property_response.data["latitude"] == -1.2676

        unit_response = client.post(
            f"/api/v1/properties/{property_response.data['id']}/units/",
            {"unit_number": "A03", "title": "One bedroom", "unit_type": "apartment", "monthly_rent": 26000, "bedrooms": 1, "amenities": [amenity.id]},
            format="json",
        )
        assert unit_response.status_code == 201
        assert unit_response.data["slug"] == "nairobi-westlands-one-bedroom-a03"
        assert unit_response.data["amenity_details"][0]["name"] == "Borehole"

    def test_landlord_cannot_change_another_landlords_unit(self):
        owner = landlord()
        other = landlord("+254700000002")
        property = Property.objects.create(landlord=owner.landlord_profile, name="Kilele", address_line="1 Road", area="Kilimani", city="Nairobi", county="Nairobi")
        unit = Unit.objects.create(property=property, unit_number="1", title="Studio", unit_type="studio", monthly_rent=15000)
        client = APIClient()
        client.force_authenticate(other)

        response = client.patch(f"/api/v1/properties/units/{unit.id}/", {"monthly_rent": 1}, format="json")
        assert response.status_code == 404
        unit.refresh_from_db()
        assert unit.monthly_rent == 15000

    def test_tenant_cannot_create_a_listing(self):
        tenant = User.objects.create_user(username="tenant", phone_number="+254700000003", role=User.Role.TENANT)
        client = APIClient()
        client.force_authenticate(tenant)
        response = client.post("/api/v1/properties/mine/", property_payload(), format="json")
        assert response.status_code == 403

    def test_public_search_filters_and_returns_paginated_results(self):
        owner = landlord()
        property = Property.objects.create(landlord=owner.landlord_profile, name="Green Apartments", address_line="12 Road", area="Westlands", city="Nairobi", county="Nairobi")
        Unit.objects.create(property=property, unit_number="A1", title="Bright studio", unit_type="studio", monthly_rent=18000, bedrooms=0, is_published=True)
        client = APIClient()
        response = client.get("/api/v1/properties/search/?city=nairobi&min_rent=10000&max_rent=20000&bedrooms=0")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["title"] == "Bright studio"
        assert response.data["results"][0]["property"]["area"] == "Westlands"

    def test_public_search_returns_validation_error_for_bad_filters(self):
        response = APIClient().get("/api/v1/properties/search/?min_rent=30000&max_rent=10000")
        assert response.status_code == 400
        assert "error" in response.data

    def test_tenant_can_save_and_remove_a_unit(self):
        owner = landlord()
        property = Property.objects.create(landlord=owner.landlord_profile, name="Green Apartments", address_line="12 Road", area="Westlands", city="Nairobi", county="Nairobi")
        unit = Unit.objects.create(property=property, unit_number="A2", title="Sunny one bedroom", unit_type="apartment", monthly_rent=25000, bedrooms=1, is_published=True)
        tenant = User.objects.create_user(username="tenant-saved", phone_number="+254700000003", role="tenant")
        TenantProfile.objects.create(user=tenant)
        client = APIClient()
        client.force_authenticate(tenant)
        saved = client.post("/api/v1/properties/saved/", {"unit_id": unit.id}, format="json")
        assert saved.status_code == 201
        assert saved.data["unit"]["property"]["area"] == "Westlands"
        assert client.get("/api/v1/properties/saved/").data[0]["unit"]["id"] == unit.id
        assert client.delete(f"/api/v1/properties/saved/{unit.id}/").status_code == 204

    def test_landlord_cannot_access_saved_units(self):
        owner = landlord()
        client = APIClient()
        client.force_authenticate(owner)
        assert client.get("/api/v1/properties/saved/").status_code == 403
