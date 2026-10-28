"""Tests for the cellar sync API endpoint and serialization helpers."""

import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from wine_cellar.apps.core.api import (
    _storage_item_to_dict,
    _storage_to_dict,
    _wine_to_dict,
)


@pytest.mark.django_db
class TestStorageToDict:
    def test_basic_fields(self, storage_factory, user):
        storage = storage_factory(
            user=user,
            name="Fridge",
            location="Kitchen",
            rows=3,
            columns=4,
        )
        result = _storage_to_dict(storage)
        assert result["id"] == storage.pk
        assert result["name"] == "Fridge"
        assert result["location"] == "Kitchen"
        assert result["rows"] == 3
        assert result["columns"] == 4
        assert "is_cold" in result
        assert "order" in result
        assert "is_default" in result


@pytest.mark.django_db
class TestStorageItemToDict:
    def test_basic_fields(self, storage_item_factory, user, wine_factory):
        wine = wine_factory(user=user, name="Merlot")
        storage = user.storage_set.first()
        item = storage_item_factory(
            storage=storage,
            wine=wine,
            user=user,
            price="19.99",
            is_gift=True,
            gift_from="Alice",
            occasion="Birthday",
        )
        result = _storage_item_to_dict(item, "wine")
        assert result["id"] == item.pk
        assert result["beverage_id"] == wine.pk
        assert result["storage_id"] == storage.pk
        assert result["storage_name"] == storage.name
        assert result["price"] == "19.99"
        assert result["is_gift"] is True
        assert result["gift_from"] == "Alice"
        assert result["occasion"] == "Birthday"

    def test_null_price(self, storage_item_factory, user, wine_factory):
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        item = storage_item_factory(storage=storage, wine=wine, user=user, price=None)
        result = _storage_item_to_dict(item, "wine")
        assert result["price"] is None

    def test_empty_optional_fields(self, storage_item_factory, user, wine_factory):
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        item = storage_item_factory(
            storage=storage, wine=wine, user=user, gift_from="", occasion=""
        )
        result = _storage_item_to_dict(item, "wine")
        assert result["gift_from"] == ""
        assert result["occasion"] == ""


@pytest.mark.django_db
class TestWineToDict:
    def test_basic_fields(self, user, wine_factory):
        wine = wine_factory(
            user=user,
            name="Château Margaux",
            vintage=2015,
            country="FR",
            abv=13.5,
            rating=5,
            comment="Excellent",
        )
        from wine_cellar.apps.wine.models import Wine

        wine = Wine.objects.filter(pk=wine.pk).with_related().with_stock_count().get()
        result = _wine_to_dict(wine)
        assert result["id"] == wine.pk
        assert result["name"] == "Château Margaux"
        assert result["vintage"] == 2015
        assert result["country"] == "FR"
        assert result["abv"] == 13.5
        assert result["rating"] == 5
        assert result["comment"] == "Excellent"
        assert "type" in result
        assert "type_code" in result
        assert "grapes" in result
        assert isinstance(result["grapes"], list)
        assert "stock_count" in result
        assert "modified" in result

    def test_null_optional_fields(self, user, wine_factory):
        wine = wine_factory(
            user=user,
            vintage=None,
            abv=None,
            rating=None,
            price=None,
        )
        from wine_cellar.apps.wine.models import Wine

        wine = Wine.objects.filter(pk=wine.pk).with_related().with_stock_count().get()
        result = _wine_to_dict(wine)
        assert result["vintage"] is None
        assert result["abv"] is None
        assert result["rating"] is None
        assert result["price"] is None


@pytest.mark.django_db
class TestApiCellarSync:
    url = reverse("api-cellar-sync")

    def test_requires_auth(self, client):
        response = client.get(self.url)
        # LoginRequiredMiddleware redirects to login
        assert response.status_code in (302, 403)

    def test_requires_get(self, client, user):
        client.force_login(user)
        response = client.post(self.url)
        assert response.status_code == 405

    def test_returns_json(self, client, user):
        client.force_login(user)
        response = client.get(self.url)
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"

    def test_response_structure(self, client, user):
        client.force_login(user)
        response = client.get(self.url)
        data = json.loads(response.content)
        assert "app_type" in data
        assert "currency" in data
        assert "beverages" in data
        assert "deleted_beverage_ids" in data
        assert "stock_items" in data
        assert "deleted_stock_item_ids" in data
        assert "storages" in data
        assert "is_incremental" in data
        assert data["is_incremental"] is False

    def test_includes_wines(self, client, user, wine_factory):
        wine_factory(user=user, name="Test Pinot")
        client.force_login(user)
        response = client.get(self.url)
        data = json.loads(response.content)
        names = [b["name"] for b in data["beverages"]]
        assert "Test Pinot" in names

    def test_excludes_deleted_wines(self, client, user, wine_factory):
        wine_factory(user=user, name="Visible Wine")
        wine_factory(user=user, name="Deleted Wine", deleted=True)
        client.force_login(user)
        response = client.get(self.url)
        data = json.loads(response.content)
        names = [b["name"] for b in data["beverages"]]
        assert "Visible Wine" in names
        assert "Deleted Wine" not in names

    def test_includes_stock_items(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user, name="Stocked Wine")
        storage = user.storage_set.first()
        storage_item_factory(storage=storage, wine=wine, user=user)
        client.force_login(user)
        response = client.get(self.url)
        data = json.loads(response.content)
        assert len(data["stock_items"]) >= 1
        assert data["stock_items"][0]["beverage_id"] == wine.pk

    def test_includes_storages(self, client, user):
        client.force_login(user)
        response = client.get(self.url)
        data = json.loads(response.content)
        # User factory creates a default storage
        assert len(data["storages"]) >= 1

    def test_scoped_to_household(self, client, user, user_factory, wine_factory):
        other_user = user_factory()
        wine_factory(user=other_user, name="Other User Wine")
        wine_factory(user=user, name="My Wine")
        client.force_login(user)
        response = client.get(self.url)
        data = json.loads(response.content)
        names = [b["name"] for b in data["beverages"]]
        assert "My Wine" in names
        assert "Other User Wine" not in names

    def test_incremental_sync_with_since(self, client, user, wine_factory):
        wine = wine_factory(user=user, name="Old Wine")
        # Move modified time to the past
        from wine_cellar.apps.wine.models import Wine

        past = timezone.now() - timedelta(hours=2)
        Wine.objects.filter(pk=wine.pk).update(modified=past)

        wine_factory(user=user, name="New Wine")

        since = (timezone.now() - timedelta(hours=1)).isoformat()
        client.force_login(user)
        response = client.get(self.url, {"since": since})
        data = json.loads(response.content)
        assert data["is_incremental"] is True
        names = [b["name"] for b in data["beverages"]]
        assert "New Wine" in names
        assert "Old Wine" not in names

    def test_incremental_sync_reports_deleted_wines(self, client, user, wine_factory):
        wine = wine_factory(user=user, name="Deleted Later")
        since = wine.modified.isoformat()
        wine.deleted = True
        wine.save_with_modified(update_fields=["deleted"])

        client.force_login(user)
        response = client.get(self.url, {"since": since})
        data = json.loads(response.content)

        assert data["is_incremental"] is True
        assert data["beverages"] == []
        assert data["deleted_beverage_ids"] == [wine.pk]

    def test_incremental_sync_reports_consumed_bottles(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user, name="Consumable Wine")
        storage = user.storage_set.first()
        bottle = storage_item_factory(storage=storage, wine=wine, user=user)
        since = bottle.modified.isoformat()

        client.force_login(user)
        response = client.post(
            reverse("drink-record-add", kwargs={"pk": wine.pk}),
            {
                "date_consumed": "2024-01-15",
                "storage_item": bottle.pk,
            },
        )
        assert response.status_code == 302

        sync_response = client.get(self.url, {"since": since})
        data = json.loads(sync_response.content)

        assert data["is_incremental"] is True
        assert data["stock_items"] == []
        assert data["deleted_stock_item_ids"] == [bottle.pk]

    def test_invalid_since_returns_400(self, client, user):
        client.force_login(user)
        response = client.get(self.url, {"since": "not-a-date"})
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_currency_from_user_settings(self, client, user):
        from wine_cellar.apps.user.models import UserSettings

        settings = UserSettings.objects.get(user=user)
        settings.currency = "USD"
        settings.save()
        client.force_login(user)
        response = client.get(self.url)
        data = json.loads(response.content)
        assert data["currency"] == "USD"
