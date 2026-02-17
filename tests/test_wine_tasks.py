from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from wine_cellar.apps.user.views import get_user_settings
from wine_cellar.apps.wine.models import PriceHistory, SaleAlert
from wine_cellar.apps.wine.tasks import check_sale_alerts, fetch_wine_prices


@pytest.mark.django_db
def test_check_sale_alerts_sends_when_threshold_met(user, wine_factory, source_factory):
    wine = wine_factory(user=user)
    source = source_factory()
    wine.source.add(source)

    alert = SaleAlert.objects.create(
        user=user,
        wine=wine,
        source=source,
        threshold_price=Decimal("9.00"),
        threshold_percent=10,
        is_active=True,
        household=wine.household,
    )

    PriceHistory.objects.create(
        wine=wine,
        source=source,
        price=Decimal("12.00"),
        user=user,
        household=wine.household,
        recorded_at=timezone.now() - timezone.timedelta(days=2),
    )
    PriceHistory.objects.create(
        wine=wine,
        source=source,
        price=Decimal("8.50"),
        user=user,
        household=wine.household,
        recorded_at=timezone.now(),
    )

    with patch("wine_cellar.apps.wine.tasks.send_sale_alert") as send_sale_alert:
        check_sale_alerts()
        send_sale_alert.assert_called_once()
        alert.refresh_from_db()
        assert alert.last_notified is not None


@pytest.mark.django_db
def test_check_sale_alerts_skips_without_active_household(
    user, wine_factory, source_factory
):
    settings = get_user_settings(user)
    settings.active_household = None
    settings.save()

    wine = wine_factory(user=user)
    source = source_factory()
    wine.source.add(source)

    SaleAlert.objects.create(
        user=user,
        wine=wine,
        source=source,
        threshold_price=Decimal("9.00"),
        threshold_percent=10,
        is_active=True,
        household=wine.household,
    )

    with patch("wine_cellar.apps.wine.tasks.send_sale_alert") as send_sale_alert:
        check_sale_alerts()
        send_sale_alert.assert_not_called()


@pytest.mark.django_db
def test_fetch_wine_prices_records_price(user, wine_factory, source_factory):
    wine = wine_factory(user=user, price_url="https://example.com")
    source = source_factory(price_selector=".price")
    wine.source.add(source)

    class MockResponse:
        text = '<span class="price">$12.99</span>'

        def raise_for_status(self):
            return None

    with patch("wine_cellar.apps.wine.tasks.requests.get", return_value=MockResponse()):
        result = fetch_wine_prices()

    assert "Fetched" in result
    assert PriceHistory.objects.filter(wine=wine, source=source).exists()
