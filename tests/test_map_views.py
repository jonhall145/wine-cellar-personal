import pytest
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed


@pytest.mark.django_db
class TestWineMapView:
    def test_unauthenticated_redirects(self, client):
        r = client.get(reverse("wine-map"), follow=True)
        assert r.status_code == 200
        assert "login" in r.request["PATH_INFO"]

    def test_renders_map(self, client, user):
        client.force_login(user)
        r = client.get(reverse("wine-map"))
        assert r.status_code == 200
        assertTemplateUsed(r, "wine_map.html")

    def test_context_includes_wines_with_stock(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine_in_stock = wine_factory(user=user, name="In Stock Wine")
        storage = user.storage_set.first()
        storage_item_factory(wine=wine_in_stock, storage=storage)

        wine_no_stock = wine_factory(user=user, name="No Stock Wine")

        client.force_login(user)
        r = client.get(reverse("wine-map"))
        wines = list(r.context["wines"])
        wine_ids = [w.pk for w in wines]
        assert wine_in_stock.pk in wine_ids
        assert wine_no_stock.pk not in wine_ids

    def test_excludes_deleted_wines(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user, deleted=True)
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage)

        client.force_login(user)
        r = client.get(reverse("wine-map"))
        assert wine.pk not in [w.pk for w in r.context["wines"]]

    def test_excludes_deleted_storage_items(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage, deleted=True)

        client.force_login(user)
        r = client.get(reverse("wine-map"))
        assert wine.pk not in [w.pk for w in r.context["wines"]]
