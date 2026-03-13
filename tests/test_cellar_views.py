import pytest
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed


@pytest.mark.django_db
class TestCellarValueView:
    def test_renders(self, client, user):
        client.force_login(user)
        r = client.get(reverse("cellar-value"))
        assert r.status_code == 200
        assertTemplateUsed(r, "core/cellar_value.html")

    def test_groupings_with_data(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user, country="FR", wine_type="RE")
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage, price=20)
        client.force_login(user)
        r = client.get(reverse("cellar-value"))
        assert r.status_code == 200

    def test_groupings_unknown_country(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user, country="", wine_type="")
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage, price=10)
        client.force_login(user)
        r = client.get(reverse("cellar-value"))
        assert r.status_code == 200


@pytest.mark.django_db
class TestConsumptionStatsView:
    def test_renders(self, client, user):
        client.force_login(user)
        r = client.get(reverse("consumption-stats"))
        assert r.status_code == 200
        assertTemplateUsed(r, "core/consumption_stats.html")


@pytest.mark.django_db
class TestStatsDashboardView:
    def test_renders(self, client, user):
        client.force_login(user)
        r = client.get(reverse("stats-dashboard"))
        assert r.status_code == 200
        assertTemplateUsed(r, "core/stats_dashboard.html")

    def test_with_stock_data(self, client, user, wine_factory, storage_item_factory):
        wine = wine_factory(user=user, country="IT", wine_type="WH")
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage, price=15)
        client.force_login(user)
        r = client.get(reverse("stats-dashboard"))
        assert r.status_code == 200
