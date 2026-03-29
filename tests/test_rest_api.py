"""Tests for the REST API (DRF)."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from wine_cellar.apps.api.models import APIKey, APIKeyScope
from wine_cellar.apps.household.models import (
    Household,
    HouseholdMembership,
    HouseholdRole,
    HouseholdSettings,
)
from wine_cellar.apps.storage.models import Storage, StorageItem
from wine_cellar.apps.user.models import UserSettings
from wine_cellar.apps.whisky.models import Whisky, WhiskyType
from wine_cellar.apps.wine.models import Grape, Wine, WineType


@pytest.fixture
def user(django_user_model):
    user = django_user_model.objects.create_user(
        username="apiuser", password="testpass"
    )
    household = Household.objects.create(name="Test Cellar")
    HouseholdMembership.objects.create(
        user=user, household=household, role=HouseholdRole.OWNER
    )
    HouseholdSettings.objects.create(household=household)
    settings, _ = UserSettings.objects.get_or_create(user=user)
    settings.active_household = household
    settings.save()
    return user


@pytest.fixture
def household(user):
    return user.user_settings.active_household


@pytest.fixture
def api_key_read(user, household):
    raw_key, prefix, hashed = APIKey.generate_key()
    APIKey.objects.create(
        name="read-key",
        prefix=prefix,
        hashed_key=hashed,
        user=user,
        household=household,
        scope=APIKeyScope.READ,
    )
    return raw_key


@pytest.fixture
def api_key_write(user, household):
    raw_key, prefix, hashed = APIKey.generate_key()
    APIKey.objects.create(
        name="write-key",
        prefix=prefix,
        hashed_key=hashed,
        user=user,
        household=household,
        scope=APIKeyScope.WRITE,
    )
    return raw_key


@pytest.fixture
def api_client():
    return APIClient()


# ---------------------------------------------------------------
# Authentication tests
# ---------------------------------------------------------------


@pytest.mark.django_db
class TestAuthentication:
    def test_valid_key_returns_200(self, api_client, api_key_read):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_read}")
        resp = api_client.get("/rest/wines/")
        assert resp.status_code == 200

    def test_no_auth_returns_401(self, api_client):
        resp = api_client.get("/rest/wines/")
        assert resp.status_code == 401

    def test_invalid_key_returns_401(self, api_client):
        api_client.credentials(HTTP_AUTHORIZATION="Bearer wc_invalidkeyvalue1234567890")
        resp = api_client.get("/rest/wines/")
        assert resp.status_code == 401

    def test_expired_key_returns_401(self, api_client, user, household):
        raw_key, prefix, hashed = APIKey.generate_key()
        APIKey.objects.create(
            name="expired",
            prefix=prefix,
            hashed_key=hashed,
            user=user,
            household=household,
            scope=APIKeyScope.READ,
            expires=timezone.now() - timezone.timedelta(days=1),
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw_key}")
        resp = api_client.get("/rest/wines/")
        assert resp.status_code == 401

    def test_revoked_key_returns_401(self, api_client, user, household):
        raw_key, prefix, hashed = APIKey.generate_key()
        APIKey.objects.create(
            name="revoked",
            prefix=prefix,
            hashed_key=hashed,
            user=user,
            household=household,
            scope=APIKeyScope.READ,
            is_active=False,
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw_key}")
        resp = api_client.get("/rest/wines/")
        assert resp.status_code == 401

    def test_last_used_updated(self, api_client, api_key_read):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_read}")
        api_client.get("/rest/wines/")
        key = APIKey.objects.get(prefix=api_key_read[:8])
        assert key.last_used is not None


# ---------------------------------------------------------------
# Permission / scope tests
# ---------------------------------------------------------------


@pytest.mark.django_db
class TestPermissions:
    def test_read_scope_allows_get(self, api_client, api_key_read):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_read}")
        resp = api_client.get("/rest/wines/")
        assert resp.status_code == 200

    def test_read_scope_denies_post(self, api_client, api_key_read):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_read}")
        resp = api_client.post("/rest/wines/", {"name": "Test"})
        assert resp.status_code == 403

    def test_write_scope_allows_get(self, api_client, api_key_write):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        resp = api_client.get("/rest/wines/")
        assert resp.status_code == 200

    def test_write_scope_allows_post(self, api_client, api_key_write):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        resp = api_client.post(
            "/rest/wines/",
            {"name": "Test Wine", "wine_type": "RE", "country": "FR", "vintage": 2020},
        )
        assert resp.status_code == 201


# ---------------------------------------------------------------
# Household isolation tests
# ---------------------------------------------------------------


@pytest.mark.django_db
class TestHouseholdIsolation:
    def test_cannot_see_other_household_data(
        self, api_client, api_key_read, django_user_model
    ):
        # Create wine in a different household
        other_user = django_user_model.objects.create_user(
            username="other", password="pass"
        )
        other_hh = Household.objects.create(name="Other")
        HouseholdMembership.objects.create(
            user=other_user, household=other_hh, role=HouseholdRole.OWNER
        )
        Wine.objects.create(
            name="Secret Wine",
            wine_type=WineType.RED,
            country="FR",
            user=other_user,
            household=other_hh,
        )

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_read}")
        resp = api_client.get("/rest/wines/")
        assert resp.status_code == 200
        assert resp.data["count"] == 0


# ---------------------------------------------------------------
# Wine CRUD tests
# ---------------------------------------------------------------


@pytest.mark.django_db
class TestWineCRUD:
    def test_list_wines(self, api_client, api_key_read, user, household):
        Wine.objects.create(
            name="Riesling",
            wine_type=WineType.WHITE,
            country="DE",
            user=user,
            household=household,
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_read}")
        resp = api_client.get("/rest/wines/")
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["name"] == "Riesling"

    def test_create_wine(self, api_client, api_key_write):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        resp = api_client.post(
            "/rest/wines/",
            {
                "name": "Pinot Noir",
                "wine_type": "RE",
                "country": "FR",
                "vintage": 2019,
            },
        )
        assert resp.status_code == 201
        wine = Wine.objects.get(name="Pinot Noir")
        assert wine.wine_type == "RE"
        assert wine.country == "FR"

    def test_create_wine_sets_household(self, api_client, api_key_write, household):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        api_client.post(
            "/rest/wines/",
            {"name": "Test", "wine_type": "WH", "country": "DE"},
        )
        wine = Wine.objects.get(name="Test")
        assert wine.household == household

    def test_update_wine(self, api_client, api_key_write, user, household):
        wine = Wine.objects.create(
            name="Old Name",
            wine_type=WineType.RED,
            country="FR",
            user=user,
            household=household,
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        resp = api_client.patch(
            f"/rest/wines/{wine.pk}/",
            {"name": "New Name"},
        )
        assert resp.status_code == 200
        wine.refresh_from_db()
        assert wine.name == "New Name"

    def test_delete_wine_soft_deletes(self, api_client, api_key_write, user, household):
        wine = Wine.objects.create(
            name="To Delete",
            wine_type=WineType.RED,
            country="FR",
            user=user,
            household=household,
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        resp = api_client.delete(f"/rest/wines/{wine.pk}/")
        assert resp.status_code == 204
        wine.refresh_from_db()
        assert wine.deleted is True

    def test_deleted_wines_not_listed(self, api_client, api_key_read, user, household):
        Wine.objects.create(
            name="Deleted",
            wine_type=WineType.RED,
            country="FR",
            user=user,
            household=household,
            deleted=True,
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_read}")
        resp = api_client.get("/rest/wines/")
        assert resp.data["count"] == 0

    def test_wine_with_m2m(self, api_client, api_key_write, user, household):
        grape = Grape.objects.create(name="Riesling", user=user, household=household)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        resp = api_client.post(
            "/rest/wines/",
            {
                "name": "M2M Test",
                "wine_type": "WH",
                "country": "DE",
                "grapes": [grape.pk],
            },
        )
        assert resp.status_code == 201
        wine = Wine.objects.get(name="M2M Test")
        assert grape in wine.grapes.all()

    def test_retrieve_wine_has_nested_data(
        self, api_client, api_key_read, user, household
    ):
        grape = Grape.objects.create(name="Cab Sauv", user=user, household=household)
        wine = Wine.objects.create(
            name="Nested Test",
            wine_type=WineType.RED,
            country="FR",
            user=user,
            household=household,
        )
        wine.grapes.add(grape)

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_read}")
        resp = api_client.get(f"/rest/wines/{wine.pk}/")
        assert resp.status_code == 200
        assert len(resp.data["grapes"]) == 1
        assert resp.data["grapes"][0]["name"] == "Cab Sauv"


# ---------------------------------------------------------------
# Reference data tests
# ---------------------------------------------------------------


@pytest.mark.django_db
class TestReferenceData:
    def test_appellations_list(self, api_client, api_key_read):
        from wine_cellar.apps.wine.models import Appellation

        Appellation.objects.get_or_create(
            name="Mosel",
            country="DE",
            defaults={"latitude": 50.0, "longitude": 7.0},
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_read}")
        resp = api_client.get("/rest/appellations/")
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_grapes_crud(self, api_client, api_key_write, user, household):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        # Create
        resp = api_client.post("/rest/grapes/", {"name": "Merlot"})
        assert resp.status_code == 201
        grape_id = resp.data["id"]
        # Read
        resp = api_client.get(f"/rest/grapes/{grape_id}/")
        assert resp.data["name"] == "Merlot"
        # Update
        resp = api_client.patch(f"/rest/grapes/{grape_id}/", {"name": "Merlot Updated"})
        assert resp.status_code == 200
        # Delete
        resp = api_client.delete(f"/rest/grapes/{grape_id}/")
        assert resp.status_code == 204
        assert not Grape.objects.filter(pk=grape_id).exists()


# ---------------------------------------------------------------
# Storage tests
# ---------------------------------------------------------------


@pytest.mark.django_db
class TestStorageAPI:
    def test_list_storages(self, api_client, api_key_read, user, household):
        from wine_cellar.apps.storage.models import Storage

        Storage.objects.create(
            name="Wine Rack",
            location="Kitchen",
            user=user,
            household=household,
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_read}")
        resp = api_client.get("/rest/storages/")
        assert resp.status_code == 200
        assert resp.data["count"] == 1


# ---------------------------------------------------------------
# Management command tests
# ---------------------------------------------------------------


@pytest.mark.django_db
class TestManagementCommands:
    def test_create_api_key(self, user, household):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command(
            "create_api_key",
            name="test-key",
            user=user.username,
            household=str(household.pk),
            scope="write",
            stdout=out,
        )
        output = out.getvalue()
        assert "wc_" in output
        assert APIKey.objects.filter(name="test-key").exists()

    def test_list_api_keys(self, user, household):
        from io import StringIO

        from django.core.management import call_command

        raw_key, prefix, hashed = APIKey.generate_key()
        APIKey.objects.create(
            name="list-test",
            prefix=prefix,
            hashed_key=hashed,
            user=user,
            household=household,
            scope=APIKeyScope.READ,
        )
        out = StringIO()
        call_command("list_api_keys", stdout=out)
        assert "list-test" in out.getvalue()

    def test_revoke_api_key(self, user, household):
        from io import StringIO

        from django.core.management import call_command

        raw_key, prefix, hashed = APIKey.generate_key()
        APIKey.objects.create(
            name="revoke-test",
            prefix=prefix,
            hashed_key=hashed,
            user=user,
            household=household,
            scope=APIKeyScope.READ,
        )
        out = StringIO()
        call_command("revoke_api_key", "revoke-test", stdout=out)
        key = APIKey.objects.get(name="revoke-test")
        assert key.is_active is False


# ---------------------------------------------------------------
# APIKey model tests
# ---------------------------------------------------------------


@pytest.mark.django_db
class TestAPIKeyModel:
    def test_generate_key_format(self):
        raw, prefix, hashed = APIKey.generate_key()
        assert raw.startswith("wc_")
        assert len(prefix) == 8
        assert len(hashed) == 64  # SHA-256 hex

    def test_scope_hierarchy(self, user, household):
        raw, prefix, hashed = APIKey.generate_key()
        key = APIKey.objects.create(
            name="test",
            prefix=prefix,
            hashed_key=hashed,
            user=user,
            household=household,
            scope=APIKeyScope.WRITE,
        )
        assert key.has_scope(APIKeyScope.READ) is True
        assert key.has_scope(APIKeyScope.WRITE) is True
        assert key.has_scope(APIKeyScope.ADMIN) is False

    def test_is_valid(self, user, household):
        raw, prefix, hashed = APIKey.generate_key()
        key = APIKey.objects.create(
            name="test",
            prefix=prefix,
            hashed_key=hashed,
            user=user,
            household=household,
            scope=APIKeyScope.READ,
        )
        assert key.is_valid is True
        key.is_active = False
        assert key.is_valid is False


# ---------------------------------------------------------------
# API root / DefaultRouter
# ---------------------------------------------------------------


@pytest.mark.django_db
class TestAPIRoot:
    def test_api_root_returns_endpoint_list(self, api_client, api_key_read):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_read}")
        resp = api_client.get("/rest/")
        assert resp.status_code == 200
        assert "wines" in resp.data
        assert "whiskies" in resp.data
        assert "storages" in resp.data


# ---------------------------------------------------------------
# Whisky CRUD tests
# ---------------------------------------------------------------


@pytest.mark.django_db
class TestWhiskyCRUD:
    def test_list_whiskies(self, api_client, api_key_read, user, household):
        Whisky.objects.create(
            name="Lagavulin 16",
            whisky_type=WhiskyType.SINGLE_MALT,
            country="XS",
            user=user,
            household=household,
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_read}")
        resp = api_client.get("/rest/whiskies/")
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["name"] == "Lagavulin 16"

    def test_create_whisky(self, api_client, api_key_write):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        resp = api_client.post(
            "/rest/whiskies/",
            {
                "name": "Ardbeg 10",
                "whisky_type": "SM",
                "country": "XS",
                "age_statement": 10,
            },
        )
        assert resp.status_code == 201
        whisky = Whisky.objects.get(name="Ardbeg 10")
        assert whisky.whisky_type == "SM"
        assert whisky.age_statement == 10

    def test_update_whisky(self, api_client, api_key_write, user, household):
        whisky = Whisky.objects.create(
            name="Old Name",
            whisky_type=WhiskyType.SINGLE_MALT,
            country="XS",
            user=user,
            household=household,
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        resp = api_client.patch(
            f"/rest/whiskies/{whisky.pk}/",
            {"name": "New Name"},
        )
        assert resp.status_code == 200
        whisky.refresh_from_db()
        assert whisky.name == "New Name"

    def test_delete_whisky_soft_deletes(
        self, api_client, api_key_write, user, household
    ):
        whisky = Whisky.objects.create(
            name="To Delete",
            whisky_type=WhiskyType.SINGLE_MALT,
            country="XS",
            user=user,
            household=household,
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        resp = api_client.delete(f"/rest/whiskies/{whisky.pk}/")
        assert resp.status_code == 204
        whisky.refresh_from_db()
        assert whisky.deleted is True

    def test_deleted_whiskies_not_listed(
        self, api_client, api_key_read, user, household
    ):
        Whisky.objects.create(
            name="Deleted",
            whisky_type=WhiskyType.SINGLE_MALT,
            country="XS",
            user=user,
            household=household,
            deleted=True,
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_read}")
        resp = api_client.get("/rest/whiskies/")
        assert resp.data["count"] == 0


# ---------------------------------------------------------------
# Storage item CRUD tests
# ---------------------------------------------------------------


@pytest.mark.django_db
class TestStorageItemCRUD:
    @pytest.fixture
    def storage(self, user, household):
        return Storage.objects.create(
            name="Rack A",
            location="Cellar",
            user=user,
            household=household,
        )

    @pytest.fixture
    def wine(self, user, household):
        return Wine.objects.create(
            name="Test Wine",
            wine_type=WineType.RED,
            country="FR",
            user=user,
            household=household,
        )

    def test_create_storage_item(self, api_client, api_key_write, storage, wine):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        resp = api_client.post(
            "/rest/wine-bottles/",
            {"storage": storage.pk, "wine": wine.pk},
        )
        assert resp.status_code == 201
        assert StorageItem.objects.filter(wine=wine, storage=storage).exists()

    def test_list_storage_items(
        self, api_client, api_key_read, user, household, storage, wine
    ):
        StorageItem.objects.create(
            storage=storage,
            wine=wine,
            user=user,
            household=household,
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_read}")
        resp = api_client.get("/rest/wine-bottles/")
        assert resp.status_code == 200
        assert resp.data["count"] == 1

    def test_delete_storage_item_soft_deletes_with_finished_date(
        self, api_client, api_key_write, user, household, storage, wine
    ):
        item = StorageItem.objects.create(
            storage=storage,
            wine=wine,
            user=user,
            household=household,
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        resp = api_client.delete(f"/rest/wine-bottles/{item.pk}/")
        assert resp.status_code == 204
        item.refresh_from_db()
        assert item.deleted is True
        assert item.finished_date is not None

    def test_cannot_reference_other_household_storage(
        self, api_client, api_key_write, wine, django_user_model
    ):
        """Write serializer should reject FK references to other households."""
        other_user = django_user_model.objects.create_user(
            username="other2", password="pass"
        )
        other_hh = Household.objects.create(name="Other HH")
        HouseholdMembership.objects.create(
            user=other_user, household=other_hh, role=HouseholdRole.OWNER
        )
        other_storage = Storage.objects.create(
            name="Other Rack",
            location="Other",
            user=other_user,
            household=other_hh,
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        resp = api_client.post(
            "/rest/wine-bottles/",
            {"storage": other_storage.pk, "wine": wine.pk},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------
# Storage item move history via API
# ---------------------------------------------------------------


@pytest.mark.django_db
class TestStorageItemMoveHistoryAPI:
    @pytest.fixture
    def storage(self, user, household):
        return Storage.objects.create(
            name="Rack A",
            location="Cellar",
            rows=5,
            columns=5,
            user=user,
            household=household,
        )

    @pytest.fixture
    def storage_b(self, user, household):
        return Storage.objects.create(
            name="Rack B",
            location="Kitchen",
            rows=5,
            columns=5,
            user=user,
            household=household,
        )

    @pytest.fixture
    def wine(self, user, household):
        return Wine.objects.create(
            name="Move Wine",
            wine_type=WineType.RED,
            country="FR",
            user=user,
            household=household,
        )

    def test_patch_move_creates_history(
        self, api_client, api_key_write, user, household, storage, storage_b, wine
    ):
        from wine_cellar.apps.storage.models import BottleMoveHistory

        item = StorageItem.objects.create(
            storage=storage, wine=wine, row=1, column=1,
            user=user, household=household,
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        resp = api_client.patch(
            f"/rest/wine-bottles/{item.pk}/",
            {"storage": storage_b.pk, "row": 3, "column": 2},
        )
        assert resp.status_code == 200
        history = BottleMoveHistory.objects.filter(storage_item=item)
        assert history.count() == 1
        entry = history.first()
        assert entry.from_storage == storage
        assert entry.from_row == 1
        assert entry.from_column == 1
        assert entry.to_storage == storage_b
        assert entry.to_row == 3
        assert entry.to_column == 2

    def test_patch_non_move_no_history(
        self, api_client, api_key_write, user, household, storage, wine
    ):
        from wine_cellar.apps.storage.models import BottleMoveHistory

        item = StorageItem.objects.create(
            storage=storage, wine=wine, row=1, column=1,
            user=user, household=household,
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        resp = api_client.patch(
            f"/rest/wine-bottles/{item.pk}/",
            {"price": "19.99"},
        )
        assert resp.status_code == 200
        assert BottleMoveHistory.objects.filter(storage_item=item).count() == 0

    def test_patch_rejects_occupied_position(
        self, api_client, api_key_write, user, household, storage, wine
    ):
        StorageItem.objects.create(
            storage=storage, wine=wine, row=1, column=1,
            user=user, household=household,
        )
        wine2 = Wine.objects.create(
            name="Other Wine", wine_type=WineType.WHITE, country="DE",
            user=user, household=household,
        )
        item2 = StorageItem.objects.create(
            storage=storage, wine=wine2, row=2, column=2,
            user=user, household=household,
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        resp = api_client.patch(
            f"/rest/wine-bottles/{item2.pk}/",
            {"row": 1, "column": 1},
        )
        assert resp.status_code == 400

    def test_patch_rejects_out_of_bounds(
        self, api_client, api_key_write, user, household, storage, wine
    ):
        item = StorageItem.objects.create(
            storage=storage, wine=wine, row=1, column=1,
            user=user, household=household,
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_write}")
        resp = api_client.patch(
            f"/rest/wine-bottles/{item.pk}/",
            {"row": 99, "column": 1},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------
# Pagination tests
# ---------------------------------------------------------------


@pytest.mark.django_db
class TestPagination:
    def test_pagination_fields_present(self, api_client, api_key_read):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_read}")
        resp = api_client.get("/rest/wines/")
        assert resp.status_code == 200
        assert "count" in resp.data
        assert "next" in resp.data
        assert "previous" in resp.data
        assert "results" in resp.data

    def test_limit_offset(self, api_client, api_key_read, user, household):
        for i in range(3):
            Wine.objects.create(
                name=f"Wine {i}",
                wine_type=WineType.RED,
                country="FR",
                user=user,
                household=household,
            )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_read}")
        resp = api_client.get("/rest/wines/?limit=2&offset=0")
        assert resp.status_code == 200
        assert resp.data["count"] == 3
        assert len(resp.data["results"]) == 2


# ---------------------------------------------------------------
# Global reference data cross-household tests
# ---------------------------------------------------------------


@pytest.mark.django_db
class TestGlobalReferenceData:
    def test_appellations_visible_across_households(self, api_client, api_key_read):
        from wine_cellar.apps.wine.models import Appellation

        Appellation.objects.get_or_create(
            name="Bordeaux",
            country="FR",
            defaults={"latitude": 44.8, "longitude": -0.5},
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key_read}")
        resp = api_client.get("/rest/appellations/")
        assert resp.status_code == 200
        names = [r["name"] for r in resp.data["results"]]
        assert "Bordeaux" in names


# ---------------------------------------------------------------
# Revoke command --all flag tests
# ---------------------------------------------------------------


@pytest.mark.django_db
class TestRevokeMultipleKeys:
    def test_revoke_refuses_multiple_without_all(self, user, household):
        from io import StringIO

        from django.core.management import call_command
        from django.core.management.base import CommandError

        for i in range(2):
            raw, prefix, hashed = APIKey.generate_key()
            APIKey.objects.create(
                name="dup-name",
                prefix=prefix,
                hashed_key=hashed,
                user=user,
                household=household,
                scope=APIKeyScope.READ,
            )
        with pytest.raises(CommandError, match="Found 2 keys"):
            call_command("revoke_api_key", "dup-name", stdout=StringIO())

    def test_revoke_multiple_with_all_flag(self, user, household):
        from io import StringIO

        from django.core.management import call_command

        for i in range(2):
            raw, prefix, hashed = APIKey.generate_key()
            APIKey.objects.create(
                name="dup-name2",
                prefix=prefix,
                hashed_key=hashed,
                user=user,
                household=household,
                scope=APIKeyScope.READ,
            )
        out = StringIO()
        call_command("revoke_api_key", "dup-name2", all=True, stdout=out)
        assert APIKey.objects.filter(name="dup-name2", is_active=True).count() == 0
