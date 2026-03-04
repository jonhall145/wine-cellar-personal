from decimal import Decimal
from pathlib import Path

import pytest
from django.conf import settings
from django.templatetags.static import static
from django.utils.formats import number_format

from wine_cellar.apps.user.models import UserSettings
from wine_cellar.apps.wine.models import Wine


@pytest.mark.django_db
def test_wine_model(user, wine_factory, grape_factory):
    grape = grape_factory(name="Merlot")
    wine = wine_factory(user=user, grapes=[grape])
    assert wine.get_grapes == grape.name
    assert wine.image == static("images/bottle.svg")


@pytest.mark.django_db
def test_vineyard_model(vineyard):
    assert vineyard.name == str(vineyard)


@pytest.mark.django_db
def test_food_pairing_model(food_pairing):
    assert food_pairing.name == str(food_pairing)


@pytest.mark.django_db
def test_attribute_model(attribute):
    assert attribute.name == str(attribute)


@pytest.mark.django_db
def test_wine_image(clear_image_folder, user, wine_factory, wine_image_factory):
    wine = wine_factory(user=user)
    wine_image = wine_image_factory(user=user, wine=wine)
    assert wine.image.startswith(wine_image.image.url)
    assert wine_image.image.path.startswith(
        str(settings.MEDIA_ROOT / Path(f"user_{user.pk}"))
    )


@pytest.mark.django_db
def test_get_average_price_with_currency(user, wine_factory, storage_item_factory):
    wine = wine_factory(user=user)
    storage_item_factory(wine=wine, price=10.00)
    storage_item_factory(wine=wine, price=20.00)

    avg = Decimal("15.00")
    currency = settings.CURRENCY_SYMBOLS.get("EUR")
    expected = f"{currency}{number_format(avg, use_l10n=True)}"

    assert wine.get_average_price_with_currency == expected


@pytest.mark.django_db
def test_get_average_price_no_items_returns_none(user, wine_factory):
    wine = wine_factory(user=user)
    assert wine.get_average_price_with_currency is None


@pytest.mark.django_db
def test_get_average_ignores_null_prices(user, wine_factory, storage_item_factory):
    wine = wine_factory(user=user)
    # create one item with null price and one with a price
    storage_item_factory(wine=wine)  # price is None by default
    storage_item_factory(wine=wine, price=Decimal("20.00"))

    avg = Decimal("20.00")
    currency = settings.CURRENCY_SYMBOLS.get("EUR")
    expected = f"{currency}{number_format(avg, use_l10n=True)}"
    assert wine.get_average_price_with_currency == expected


@pytest.mark.django_db
def test_get_average_all_null_prices_returns_none(
    user, wine_factory, storage_item_factory
):
    wine = wine_factory(user=user)
    storage_item_factory(wine=wine)
    storage_item_factory(wine=wine)
    assert wine.get_average_price_with_currency is None


@pytest.mark.django_db
def test_get_average_respects_user_currency(user, wine_factory, storage_item_factory):
    wine = wine_factory(user=user)
    storage_item_factory(wine=wine, price=Decimal("10.00"))
    storage_item_factory(wine=wine, price=Decimal("20.00"))

    # set user preference to USD
    us, _ = UserSettings.objects.get_or_create(user=user, defaults={"currency": "USD"})
    us.currency = "USD"
    us.save()
    avg = Decimal("15.00")
    currency = settings.CURRENCY_SYMBOLS.get(us.currency)
    expected = f"{currency}{number_format(avg, use_l10n=True)}"
    assert wine.get_average_price_with_currency == expected


@pytest.mark.django_db
def test_image_properties_use_prefetch_cache(
    user, wine_factory, wine_image_factory, clear_image_folder
):
    """Image properties should not cause extra queries when prefetch is used."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    wine = wine_factory(user=user)
    wine_image_factory(user=user, wine=wine)
    wine_image_factory(user=user, wine=wine, image_type="LB")

    # Fetch with prefetch_related — image properties should not add queries
    qs = Wine.objects.prefetch_related("wineimage_set").filter(pk=wine.pk)
    prefetched_wine = qs.first()

    # Accessing all three image properties should use the prefetch cache (0 extra)
    with CaptureQueriesContext(connection) as ctx:
        _ = prefetched_wine.image
        _ = prefetched_wine.image_thumbnail
        _ = prefetched_wine.image_thumbnails
    assert len(ctx.captured_queries) == 0, (
        f"Expected 0 queries but got {len(ctx.captured_queries)}: "
        f"{[q['sql'] for q in ctx.captured_queries]}"
    )
