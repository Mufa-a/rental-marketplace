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


@pytest.mark.django_db
class TestDeletionAndThrottling:
    def _listing(self):
        owner = landlord("+254700000041")
        prop = Property.objects.create(landlord=owner.landlord_profile, name="Hist", address_line="1 Road", area="Kilimani", city="Nairobi", county="Nairobi")
        unit = Unit.objects.create(property=prop, unit_number="1", title="Studio", unit_type="studio", monthly_rent=15000, is_published=True)
        return owner, prop, unit

    def test_deleting_a_listing_with_viewing_history_is_refused_not_a_server_error(self):
        from apps.viewings.models import ViewingRequest

        owner, prop, unit = self._listing()
        tenant = User.objects.create_user(username="t-hist", phone_number="+254700000042", role="tenant")
        ViewingRequest.objects.create(tenant=TenantProfile.objects.create(user=tenant), unit=unit)
        client = APIClient()
        client.force_authenticate(owner)
        assert client.delete(f"/api/v1/properties/units/{unit.id}/").status_code == 409
        response = client.delete(f"/api/v1/properties/{prop.id}/")
        assert response.status_code == 409
        assert response.data["error"]["code"] == "has_history"
        assert Property.objects.filter(pk=prop.id).exists() and Unit.objects.filter(pk=unit.id).exists()

    def test_deleting_a_listing_without_history_works_and_is_audited(self):
        from apps.core.models import AuditLog

        owner, _, unit = self._listing()
        client = APIClient()
        client.force_authenticate(owner)
        assert client.delete(f"/api/v1/properties/units/{unit.id}/").status_code == 204
        assert AuditLog.objects.filter(action="unit.deleted", object_id=str(unit.id)).exists()

    def test_public_search_is_rate_limited(self, monkeypatch):
        from rest_framework.throttling import ScopedRateThrottle
        monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "public_search", "3/min")
        client = APIClient()
        codes = [client.get("/api/v1/properties/search/").status_code for _ in range(5)]
        assert codes[:3] == [200, 200, 200] and codes[-1] == 429

    def test_private_tenant_and_landlord_data_is_not_in_public_listing_json(self):
        owner, _, unit = self._listing()
        body = APIClient().get("/api/v1/properties/search/").content.decode()
        detail = APIClient().get(f"/api/v1/properties/listings/{unit.slug}/").content.decode()
        for text in (body, detail):
            assert owner.phone_number not in text
            assert "landlord_id" not in text


def make_home(owner, *, area="Westlands", city="Nairobi", county="Nairobi", title="Bright studio", rent=18000, bedrooms=0,
              bathrooms=1, unit_type="studio", number="A1", location=None, address="12 Road", **unit_fields):
    from apps.properties.fields import GeographicPoint
    prop = Property.objects.create(landlord=owner.landlord_profile, name=f"{area} Court", address_line=address, area=area,
                                   city=city, county=county, location=GeographicPoint(*location) if location else None)
    return Unit.objects.create(property=prop, unit_number=number, title=title, unit_type=unit_type, monthly_rent=rent,
                               bedrooms=bedrooms, bathrooms=bathrooms, is_published=True, **unit_fields)


def search(query=""):
    response = APIClient().get(f"/api/v1/properties/search/?{query}")
    assert response.status_code == 200, response.data
    return response.data


@pytest.mark.django_db
class TestAdvancedSearch:
    def test_county_town_and_estate_filters(self):
        owner = landlord()
        make_home(owner, area="Nyali", city="Mombasa", county="Mombasa", number="1")
        make_home(owner, area="Kilimani", city="Nairobi", county="Nairobi", number="2")
        assert [r["property"]["area"] for r in search("county=mombasa")["results"]] == ["Nyali"]
        assert [r["property"]["area"] for r in search("town=nairobi")["results"]] == ["Kilimani"]
        assert [r["property"]["area"] for r in search("estate=kilim")["results"]] == ["Kilimani"]
        assert search("county=Kisumu")["count"] == 0

    def test_free_text_relevance_puts_the_estate_match_first(self):
        owner = landlord()
        make_home(owner, area="Kileleshwa", title="Roomy flat near Kilimani", number="1")
        make_home(owner, area="Kilimani", title="Garden apartment", number="2")
        data = search("q=kilimani")
        assert data["ordering"] == "relevance"
        assert [r["property"]["area"] for r in data["results"]] == ["Kilimani", "Kileleshwa"]

    def test_rent_rooms_bathrooms_type_and_every_requested_amenity(self):
        owner = landlord()
        wifi, parking = Amenity.objects.create(name="Wi-Fi"), Amenity.objects.create(name="Parking")
        both = make_home(owner, title="Two bed with both", rent=40000, bedrooms=2, bathrooms=2, unit_type="apartment", number="1")
        both.amenities.set([wifi, parking])
        one = make_home(owner, title="Two bed wifi only", rent=38000, bedrooms=2, bathrooms=1, unit_type="apartment", number="2")
        one.amenities.set([wifi])
        make_home(owner, title="Bedsitter cheap", rent=8000, number="3", unit_type="bedsitter")
        assert search("amenities=wi-fi,parking")["count"] == 1
        assert search("amenity=wi-fi")["count"] == 2
        assert search("bathrooms=2")["count"] == 1
        assert search("bedrooms=2&max_rent=39000")["count"] == 1
        assert search("unit_type=bedsitter,studio")["count"] == 1
        assert [r["monthly_rent"] for r in search("ordering=monthly_rent")["results"]] == [8000, 38000, 40000]
        assert APIClient().get("/api/v1/properties/search/?unit_type=castle").status_code == 400

    def test_unavailable_unmoderated_held_and_stale_homes_are_never_listed(self):
        from datetime import timedelta
        from django.utils import timezone
        owner = landlord()
        make_home(owner, title="Visible", number="1")
        make_home(owner, title="Let", number="2", available=False)
        make_home(owner, title="Awaiting review", number="3", moderation_status="pending_review")
        make_home(owner, title="Held", number="4", moderation_hold=True)
        stale = make_home(owner, title="Stale", number="5")
        Unit.objects.filter(pk=stale.pk).update(availability_confirmed_at=timezone.now() - timedelta(days=40))
        data = search()
        assert [r["title"] for r in data["results"]] == ["Visible"] and data["count"] == 1
        for unit in Unit.objects.exclude(title="Visible"):
            assert APIClient().get(f"/api/v1/properties/listings/{unit.slug}/").status_code == 404

    def test_distance_is_reported_and_used_for_sorting(self):
        """Regression: distance_km was always null."""
        owner = landlord()
        make_home(owner, title="Far", number="1", location=(36.90, -1.30))
        make_home(owner, title="Near", number="2", location=(36.81, -1.27))
        data = search("latitude=-1.268&longitude=36.808&radius_km=20")
        assert [r["title"] for r in data["results"]] == ["Near", "Far"]
        assert data["results"][0]["distance_km"] is not None and data["results"][0]["distance_km"] < data["results"][1]["distance_km"]

    def test_cursor_pagination_walks_every_result_once(self):
        """Regression: the frontend paged with ?page=N, which the cursor API ignored, repeating page one."""
        owner = landlord()
        for n in range(25):
            make_home(owner, title=f"Home {n:02d}", number=str(n))
        first = search()
        assert first["count"] == 25 and len(first["results"]) == 20 and first["next"]
        second = APIClient().get(first["next"]).data
        titles = [r["title"] for r in first["results"] + second["results"]]
        assert len(titles) == len(set(titles)) == 25

    def test_public_payload_has_a_canonical_path_and_no_unit_number(self):
        owner = landlord()
        make_home(owner, area="Nairobi CBD", city="Nairobi", number="SECRET-7")
        result = search()["results"][0]
        assert result["path"].startswith("/listings/nairobi/nairobi-cbd/")
        assert "unit_number" not in result and "SECRET-7" not in str({k: v for k, v in result.items() if k != "slug"})

    def test_location_suggestions_count_only_public_homes(self):
        owner = landlord()
        make_home(owner, area="Kilimani", number="1")
        make_home(owner, area="Kilimani", number="2", rent=15000)
        make_home(owner, area="Kileleshwa", number="3", available=False)
        rows = APIClient().get("/api/v1/properties/locations/?q=kil").data
        assert rows == [{"county": "Nairobi", "town": "Nairobi", "estate": "Kilimani", "listings": 2, "lowest_rent": 15000}]


@pytest.mark.django_db
class TestListingIntegrity:
    def test_rent_must_be_realistic(self):
        user = landlord()
        client = APIClient(); client.force_authenticate(user)
        prop = client.post("/api/v1/properties/mine/", property_payload(), format="json").data
        response = client.post(f"/api/v1/properties/{prop['id']}/units/", {"unit_number": "1", "title": "Bright home", "unit_type": "studio", "monthly_rent": 1}, format="json")
        assert response.status_code == 400 and "monthly_rent" in response.data["error"]["message"]

    def test_copy_of_another_landlords_listing_is_held_for_review(self):
        original_owner = landlord()
        make_home(original_owner, title="Sunny one bedroom", rent=30000, bedrooms=1, unit_type="apartment")
        copier = landlord("+254700000099")
        client = APIClient(); client.force_authenticate(copier)
        prop = client.post("/api/v1/properties/mine/", {**property_payload(), "address_line": "Elsewhere"}, format="json").data
        response = client.post(f"/api/v1/properties/{prop['id']}/units/", {"unit_number": "9", "title": "sunny ONE bedroom", "unit_type": "apartment",
                                                                              "monthly_rent": 30000, "bedrooms": 1, "is_published": True}, format="json")
        assert response.status_code == 201 and response.data["moderation_status"] == "pending_review"
        assert Unit.objects.get(pk=response.data["id"]).possible_duplicate_of is not None
        assert search("q=sunny")["count"] == 1

    def test_approval_mode_holds_new_listings(self, settings):
        settings.LISTINGS_REQUIRE_APPROVAL = True
        user = landlord()
        client = APIClient(); client.force_authenticate(user)
        prop = client.post("/api/v1/properties/mine/", property_payload(), format="json").data
        unit = client.post(f"/api/v1/properties/{prop['id']}/units/", {"unit_number": "1", "title": "Bright home", "unit_type": "studio",
                                                                         "monthly_rent": 9000, "is_published": True}, format="json").data
        assert unit["moderation_status"] == "pending_review" and search()["count"] == 0
        # Landlords cannot approve their own listing.
        client.patch(f"/api/v1/properties/units/{unit['id']}/", {"moderation_status": "approved"}, format="json")
        assert Unit.objects.get(pk=unit["id"]).moderation_status == "pending_review"

    def test_moving_a_verified_property_requires_review(self):
        user = landlord()
        prop = Property.objects.create(landlord=user.landlord_profile, name="P", address_line="1 Road", area="Kilimani", city="Nairobi",
                                       county="Nairobi", verification_status="verified")
        client = APIClient(); client.force_authenticate(user)
        client.patch(f"/api/v1/properties/{prop.id}/", {"description": "Fresh paint"}, format="json")
        prop.refresh_from_db()
        assert prop.verification_status == "verified"
        client.patch(f"/api/v1/properties/{prop.id}/", {"address_line": "99 Other Road"}, format="json")
        prop.refresh_from_db()
        assert prop.verification_status == "needs_review"

    def test_marking_occupied_closes_pending_requests_and_returns_credits(self):
        from apps.viewings.tests import marketplace
        tenant_user, tenant, landlord_user, unit = marketplace("occ")
        client = APIClient(); client.force_authenticate(tenant_user)
        request_id = client.post("/api/v1/viewings/requests/", {"unit": unit.id}, format="json").data["id"]
        client.force_authenticate(landlord_user)
        assert client.post(f"/api/v1/properties/units/{unit.id}/availability/", {"available": False}, format="json").status_code == 200
        from apps.payments.models import ViewingCreditPurchase
        from apps.viewings.models import ViewingRequest
        assert ViewingRequest.objects.get(pk=request_id).status == "cancelled"
        assert ViewingCreditPurchase.objects.get(tenant=tenant).credits_remaining == 3


@pytest.mark.django_db
class TestListingPerformance:
    def test_views_are_counted_once_per_visitor_and_reported_only_to_the_owner(self):
        owner = landlord()
        unit = make_home(owner)
        browser = {"HTTP_USER_AGENT": "Mozilla/5.0 (Android)"}
        for _ in range(3):
            APIClient().post(f"/api/v1/properties/listings/{unit.slug}/view/", **browser)
        APIClient().post(f"/api/v1/properties/listings/{unit.slug}/view/", HTTP_USER_AGENT="Googlebot/2.1")
        APIClient().post(f"/api/v1/properties/listings/{unit.slug}/view/", REMOTE_ADDR="10.0.0.9", **browser)
        client = APIClient(); client.force_authenticate(owner)
        stats = client.get("/api/v1/properties/mine/stats/").data
        assert stats["totals"]["views_30d"] == 2 and stats["units"][0]["visible_in_search"] is True

        other = landlord("+254700000098")
        client.force_authenticate(other)
        assert client.get("/api/v1/properties/mine/stats/").data["units"] == []
