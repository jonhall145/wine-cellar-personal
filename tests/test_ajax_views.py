import json

import pytest
from django.urls import reverse

from wine_cellar.apps.wine.models import WineBarcode


@pytest.mark.django_db
class TestDeleteWineBarcode:
    def test_delete_barcode(self, client, user, wine_factory, wine_barcode_factory):
        wine = wine_factory(user=user)
        barcode = wine_barcode_factory(wine=wine, user=user)
        client.force_login(user)
        r = client.post(reverse("wine-barcode-delete", kwargs={"pk": barcode.pk}))
        assert r.status_code == 200
        data = json.loads(r.content)
        assert data["success"] is True
        assert not WineBarcode.objects.filter(pk=barcode.pk).exists()

    def test_get_not_allowed(self, client, user, wine_factory, wine_barcode_factory):
        wine = wine_factory(user=user)
        barcode = wine_barcode_factory(wine=wine, user=user)
        client.force_login(user)
        r = client.get(reverse("wine-barcode-delete", kwargs={"pk": barcode.pk}))
        assert r.status_code == 405

    def test_cannot_delete_other_users_barcode(
        self, client, user, user_factory, wine_factory, wine_barcode_factory
    ):
        other = user_factory()
        wine = wine_factory(user=other)
        barcode = wine_barcode_factory(wine=wine, user=other)
        client.force_login(user)
        r = client.post(reverse("wine-barcode-delete", kwargs={"pk": barcode.pk}))
        assert r.status_code == 404


@pytest.mark.django_db
class TestExportViews:
    def test_export_csv(self, client, user, wine_factory):
        wine_factory(user=user, name="Test Merlot")
        client.force_login(user)
        r = client.get(reverse("wine-export-csv"))
        assert r.status_code == 200
        assert "text/csv" in r["Content-Type"]
        content = r.content.decode()
        assert "Test Merlot" in content

    def test_export_json(self, client, user, wine_factory):
        wine_factory(user=user, name="Test Pinot")
        client.force_login(user)
        r = client.get(reverse("wine-export-json"))
        assert r.status_code == 200
        assert "application/json" in r["Content-Type"]
        data = json.loads(r.content)
        assert any("Test Pinot" in w.get("name", "") for w in data)


@pytest.mark.django_db
class TestDuplicateCheck:
    def test_no_duplicate(self, client, user):
        client.force_login(user)
        r = client.get(reverse("wine-check-duplicate"), {"name": "Unique Wine XYZ"})
        assert r.status_code == 200
        data = json.loads(r.content)
        assert data["similar"] == []

    def test_finds_duplicate(self, client, user, wine_factory):
        wine_factory(user=user, name="Chateau Margaux")
        client.force_login(user)
        r = client.get(reverse("wine-check-duplicate"), {"name": "Chateau Margaux"})
        assert r.status_code == 200
        data = json.loads(r.content)
        assert len(data["similar"]) > 0
