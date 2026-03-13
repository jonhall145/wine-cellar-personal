from datetime import date

import pytest
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from wine_cellar.apps.wine.models import DrinkingWindowAlert


@pytest.mark.django_db
class TestDrinkingWindowAlertsView:
    def test_renders(self, client, user):
        client.force_login(user)
        r = client.get(reverse("drinking-alerts"))
        assert r.status_code == 200
        assertTemplateUsed(r, "drinking_window_alerts.html")

    def test_shows_unread_alerts(self, client, user, wine_factory):
        wine = wine_factory(user=user)
        household = wine.household
        alert = DrinkingWindowAlert.objects.create(
            wine=wine,
            user=user,
            household=household,
            alert_date=date.today(),
            is_read=False,
        )
        client.force_login(user)
        r = client.get(reverse("drinking-alerts"))
        alert_ids = [a.pk for a in r.context["alerts"]]
        assert alert.pk in alert_ids

    def test_excludes_read_alerts(self, client, user, wine_factory):
        wine = wine_factory(user=user)
        household = wine.household
        alert = DrinkingWindowAlert.objects.create(
            wine=wine,
            user=user,
            household=household,
            alert_date=date.today(),
            is_read=True,
        )
        client.force_login(user)
        r = client.get(reverse("drinking-alerts"))
        alert_ids = [a.pk for a in r.context["alerts"]]
        assert alert.pk not in alert_ids

    def test_upcoming_wines(self, client, user, wine_factory, storage_item_factory):
        current_year = date.today().year
        wine = wine_factory(user=user, drink_to=current_year)
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage)

        client.force_login(user)
        r = client.get(reverse("drinking-alerts"))
        upcoming_ids = [w.pk for w in r.context["upcoming_wines"]]
        assert wine.pk in upcoming_ids

    def test_overdue_wines(self, client, user, wine_factory, storage_item_factory):
        wine = wine_factory(user=user, drink_to=2000)
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage)

        client.force_login(user)
        r = client.get(reverse("drinking-alerts"))
        overdue_ids = [w.pk for w in r.context["overdue_wines"]]
        assert wine.pk in overdue_ids

    def test_wine_without_stock_excluded(self, client, user, wine_factory):
        wine_factory(user=user, drink_to=2000)
        client.force_login(user)
        r = client.get(reverse("drinking-alerts"))
        assert len(r.context["overdue_wines"]) == 0

    def test_wine_with_deleted_stock_excluded(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user, drink_to=2000)
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage, deleted=True)
        client.force_login(user)
        r = client.get(reverse("drinking-alerts"))
        assert len(r.context["overdue_wines"]) == 0
