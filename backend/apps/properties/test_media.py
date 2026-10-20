"""Photos and the single video on a listing: presign, register, replace, remove and public output."""

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.properties import media as media_module
from apps.properties import views as views_module
from apps.properties.models import Property, PropertyMedia, Unit
from apps.properties.tests import landlord

MB = 1024 * 1024


class FakeR2:
    """Stands in for the R2 client: `objects` is what a browser has uploaded, `deleted` what we removed."""

    def __init__(self):
        self.objects = {}
        self.deleted = []

    def put(self, key, content_type, size):
        self.objects[key] = {"ContentType": content_type, "ContentLength": size}

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise RuntimeError("404")
        return self.objects[Key]

    def delete_object(self, Bucket, Key):
        self.deleted.append(Key)
        self.objects.pop(Key, None)

    def generate_presigned_url(self, op, Params, ExpiresIn):
        return f"https://r2.example/{Params['Key']}?expires={ExpiresIn}"


@pytest.fixture
def r2(settings, monkeypatch):
    settings.AWS_ACCESS_KEY_ID = "key"
    settings.AWS_SECRET_ACCESS_KEY = "secret"
    settings.AWS_STORAGE_BUCKET_NAME = "bucket"
    settings.AWS_S3_ENDPOINT_URL = "https://r2.example"
    settings.R2_PUBLIC_BASE_URL = "https://cdn.example"
    fake = FakeR2()
    monkeypatch.setattr(views_module, "r2_client", lambda: fake)
    monkeypatch.setattr(media_module, "r2_client", lambda: fake)
    return fake


@pytest.fixture
def unit_and_client():
    owner = landlord()
    prop = Property.objects.create(landlord=owner.landlord_profile, name="Kilele", address_line="1 Road", area="Kilimani", city="Nairobi", county="Nairobi")
    unit = Unit.objects.create(
        property=prop, unit_number="1", title="Studio", unit_type="studio", monthly_rent=15000,
        availability_confirmed_at=timezone.now(), is_published=True,
    )
    client = APIClient()
    client.force_authenticate(owner)
    return unit, client


def register(client, unit, r2, content_type, size, ext, **extra):
    """Upload through the fake bucket, then register it the way the browser does."""
    key = f"properties/{unit.id}/{len(r2.objects)}-{ext.strip('.')}{ext}"
    r2.put(key, content_type, size)
    return client.post(f"/api/v1/properties/units/{unit.id}/media/", {"asset_key": key, **extra}, format="json"), key


@pytest.mark.django_db
class TestPresign:
    def url(self, unit):
        return f"/api/v1/properties/units/{unit.id}/media/presign/"

    def test_video_presign_is_scoped_to_the_unit_and_lasts_longer_than_a_photo(self, r2, unit_and_client):
        unit, client = unit_and_client
        video = client.post(self.url(unit), {"filename": "tour.mp4", "content_type": "video/mp4", "size": 20 * MB}, format="json")
        photo = client.post(self.url(unit), {"filename": "a.jpg", "content_type": "image/jpeg"}, format="json")
        assert video.status_code == photo.status_code == 200
        assert video.data["asset_key"].startswith(f"properties/{unit.id}/") and video.data["asset_key"].endswith(".mp4")
        assert video.data["expires_in_seconds"] > photo.data["expires_in_seconds"]

    @pytest.mark.parametrize("body", [
        {"filename": "tour.mp4", "content_type": "video/mp4", "size": 100 * MB + 1},   # video too big
        {"filename": "a.jpg", "content_type": "image/jpeg", "size": 10 * MB + 1},      # photo too big
        {"filename": "tour.avi", "content_type": "video/x-msvideo"},                   # unsupported type
        {"filename": "tour.mov", "content_type": "video/mp4"},                         # extension / type mismatch
        {"filename": "../tour.mp4", "content_type": "video/mp4"},                      # a path, not a filename
        {"filename": "evil.html", "content_type": "text/html"},
    ])
    def test_refused_before_uploading(self, r2, unit_and_client, body):
        unit, client = unit_and_client
        assert client.post(self.url(unit), body, format="json").status_code == 400

    def test_photo_presign_refused_at_the_photo_limit_but_video_is_still_allowed(self, r2, unit_and_client, settings):
        unit, client = unit_and_client
        settings.MEDIA_MAX_PHOTOS_PER_UNIT = 1
        PropertyMedia.objects.create(unit=unit, asset_key=f"properties/{unit.id}/x.jpg")
        assert client.post(self.url(unit), {"filename": "b.jpg", "content_type": "image/jpeg"}, format="json").status_code == 400
        assert client.post(self.url(unit), {"filename": "t.mp4", "content_type": "video/mp4"}, format="json").status_code == 200

    def test_another_landlord_cannot_presign_for_the_unit(self, r2, unit_and_client):
        unit, _ = unit_and_client
        intruder = APIClient()
        intruder.force_authenticate(landlord("+254700000009"))
        assert intruder.post(self.url(unit), {"filename": "a.jpg", "content_type": "image/jpeg"}, format="json").status_code == 404


@pytest.mark.django_db
class TestRegister:
    def test_several_photos_and_one_video_register(self, r2, unit_and_client):
        unit, client = unit_and_client
        for ext in (".jpg", ".png", ".webp"):
            response, _ = register(client, unit, r2, {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}[ext], 2 * MB, ext)
            assert response.status_code == 201 and response.data["kind"] == "image"
        response, _ = register(client, unit, r2, "video/mp4", 50 * MB, ".mp4")
        assert response.status_code == 201 and response.data["kind"] == "video"
        assert response.data["media_type"] == "video"  # derived from the stored file, not the request
        assert unit.media.count() == 4

    def test_a_photo_cannot_claim_to_be_the_video(self, r2, unit_and_client):
        unit, client = unit_and_client
        response, _ = register(client, unit, r2, "image/jpeg", MB, ".jpg", media_type="video")
        assert response.status_code == 201 and response.data["media_type"] == "other"
        assert not unit.media.filter(media_type="video").exists()

    def test_a_second_video_replaces_the_first_and_removes_its_file(self, r2, unit_and_client):
        unit, client = unit_and_client
        _, first_key = register(client, unit, r2, "video/mp4", 10 * MB, ".mp4")
        response, second_key = register(client, unit, r2, "video/webm", 10 * MB, ".webm")
        assert response.status_code == 201
        assert list(unit.media.values_list("asset_key", flat=True)) == [second_key]
        assert first_key in r2.deleted and second_key not in r2.deleted

    def test_oversize_video_is_refused_and_deleted_from_the_bucket(self, r2, unit_and_client):
        unit, client = unit_and_client
        response, key = register(client, unit, r2, "video/mp4", 100 * MB + 1, ".mp4")
        assert response.status_code == 400 and "100 MB" in response.json()["error"]["message"]
        assert key in r2.deleted and unit.media.count() == 0

    def test_oversize_photo_is_refused_and_deleted(self, r2, unit_and_client):
        unit, client = unit_and_client
        response, key = register(client, unit, r2, "image/jpeg", 10 * MB + 1, ".jpg")
        assert response.status_code == 400 and key in r2.deleted

    def test_wrong_stored_type_is_refused_even_if_the_filename_looks_fine(self, r2, unit_and_client):
        unit, client = unit_and_client
        response, key = register(client, unit, r2, "text/html", 1000, ".jpg")
        assert response.status_code == 400 and key in r2.deleted and unit.media.count() == 0

    def test_photo_limit_is_enforced_on_register_and_the_extra_file_is_deleted(self, r2, unit_and_client, settings):
        unit, client = unit_and_client
        settings.MEDIA_MAX_PHOTOS_PER_UNIT = 2
        assert register(client, unit, r2, "image/jpeg", MB, ".jpg")[0].status_code == 201
        assert register(client, unit, r2, "image/png", MB, ".png")[0].status_code == 201
        response, key = register(client, unit, r2, "image/webp", MB, ".webp")
        assert response.status_code == 400 and "at most 2 photos" in response.json()["error"]["message"]
        assert key in r2.deleted and unit.media.count() == 2

    def test_the_video_does_not_count_toward_the_photo_limit(self, r2, unit_and_client, settings):
        unit, client = unit_and_client
        settings.MEDIA_MAX_PHOTOS_PER_UNIT = 1
        assert register(client, unit, r2, "image/jpeg", MB, ".jpg")[0].status_code == 201
        assert register(client, unit, r2, "video/mp4", MB, ".mp4")[0].status_code == 201

    def test_unverified_upload_and_foreign_key_are_refused(self, r2, unit_and_client):
        unit, client = unit_and_client
        url = f"/api/v1/properties/units/{unit.id}/media/"
        assert client.post(url, {"asset_key": f"properties/{unit.id}/never-uploaded.mp4"}, format="json").status_code == 400
        r2.put("properties/999999/x.jpg", "image/jpeg", MB)
        assert client.post(url, {"asset_key": "properties/999999/x.jpg"}, format="json").status_code == 400
        assert unit.media.count() == 0 and r2.deleted == []  # another unit's file is never deleted by us

    def test_registering_the_same_key_twice_does_not_delete_the_live_file(self, r2, unit_and_client):
        unit, client = unit_and_client
        response, key = register(client, unit, r2, "image/jpeg", MB, ".jpg")
        assert response.status_code == 201
        again = client.post(f"/api/v1/properties/units/{unit.id}/media/", {"asset_key": key}, format="json")
        assert again.status_code == 400 and r2.deleted == [] and key in r2.objects

    def test_database_allows_only_one_video_per_unit(self, unit_and_client):
        unit, _ = unit_and_client
        PropertyMedia.objects.create(unit=unit, asset_key="a.mp4", media_type="video")
        with pytest.raises(IntegrityError), transaction.atomic():
            PropertyMedia.objects.create(unit=unit, asset_key="b.mp4", media_type="video")
        PropertyMedia.objects.create(unit=unit, asset_key="c.jpg")
        PropertyMedia.objects.create(unit=unit, asset_key="d.jpg")


@pytest.mark.django_db
class TestRemoveAndPublicOutput:
    def test_removing_a_file_deletes_the_row_and_the_stored_object(self, r2, unit_and_client):
        unit, client = unit_and_client
        response, key = register(client, unit, r2, "video/mp4", MB, ".mp4")
        assert client.delete(f"/api/v1/properties/media/{response.data['id']}/").status_code == 204
        assert unit.media.count() == 0 and key in r2.deleted

    def test_another_landlord_cannot_remove_it(self, r2, unit_and_client):
        unit, client = unit_and_client
        response, key = register(client, unit, r2, "image/jpeg", MB, ".jpg")
        intruder = APIClient()
        intruder.force_authenticate(landlord("+254700000009"))
        assert intruder.delete(f"/api/v1/properties/media/{response.data['id']}/").status_code == 403
        assert unit.media.count() == 1 and r2.deleted == []

    def test_public_listing_separates_photos_from_the_video(self, r2, unit_and_client):
        unit, client = unit_and_client
        register(client, unit, r2, "image/jpeg", MB, ".jpg")
        register(client, unit, r2, "image/png", MB, ".png")
        _, video_key = register(client, unit, r2, "video/mp4", MB, ".mp4")
        data = APIClient().get(f"/api/v1/properties/listings/{unit.slug}/").json()
        assert [m["kind"] for m in data["media"]] == ["image", "image"]
        assert data["video"]["url"] == f"https://cdn.example/{video_key}" and data["video"]["kind"] == "video"

    def test_listing_without_a_video_has_video_null(self, r2, unit_and_client):
        unit, client = unit_and_client
        register(client, unit, r2, "image/jpeg", MB, ".jpg")
        assert APIClient().get(f"/api/v1/properties/listings/{unit.slug}/").json()["video"] is None

    def test_search_cards_never_receive_the_video_as_an_image(self, r2, unit_and_client):
        unit, client = unit_and_client
        register(client, unit, r2, "video/mp4", MB, ".mp4")
        results = APIClient().get("/api/v1/properties/search/").json()["results"]
        assert results and results[0]["media"] == [] and results[0]["video"] is not None

    def test_storage_failure_when_deleting_does_not_break_removal(self, r2, unit_and_client, monkeypatch):
        unit, client = unit_and_client
        response, _ = register(client, unit, r2, "image/jpeg", MB, ".jpg")

        def boom(**_):
            raise RuntimeError("R2 down")

        monkeypatch.setattr(r2, "delete_object", boom)
        assert client.delete(f"/api/v1/properties/media/{response.data['id']}/").status_code == 204
        assert unit.media.count() == 0
