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
def test_get_vineyards(user, wine_factory, vineyard_factory):
    v1 = vineyard_factory(name="Vineyard A")
    v2 = vineyard_factory(name="Vineyard B")
    wine = wine_factory(user=user)
    wine.vineyard.set([v1, v2])
    vineyards = wine.get_vineyards
    assert "Vineyard A" in vineyards
    assert "Vineyard B" in vineyards


@pytest.mark.django_db
def test_get_grapes_multiple(user, wine_factory, grape_factory):
    g1 = grape_factory(name="Merlot")
    g2 = grape_factory(name="Cabernet")
    wine = wine_factory(user=user, grapes=[g1, g2])
    grapes = wine.get_grapes
    assert "Merlot" in grapes
    assert "Cabernet" in grapes


@pytest.mark.django_db
def test_get_sources(user, wine_factory, source_factory):
    s1 = source_factory(name="Shop A")
    s2 = source_factory(name="Shop B")
    wine = wine_factory(user=user)
    wine.source.set([s1, s2])
    sources = wine.get_sources
    assert "Shop A" in sources
    assert "Shop B" in sources


@pytest.mark.django_db
def test_country_icon(user, wine_factory):
    wine = wine_factory(user=user, country="DE")
    assert wine.country_icon == "🇩🇪"


@pytest.mark.django_db
def test_total_stock(user, wine_factory, storage_item_factory):
    wine = wine_factory(user=user)
    storage_item_factory(wine=wine, deleted=False)
    storage_item_factory(wine=wine, deleted=False)
    storage_item_factory(wine=wine, deleted=True)
    assert wine.total_stock == 2


@pytest.mark.django_db
def test_str_with_vintage(user, wine_factory):
    wine = wine_factory(user=user, name="Riesling", vintage=2020)
    assert str(wine) == "Riesling (2020)"


@pytest.mark.django_db
def test_str_without_vintage(user, wine_factory):
    wine = wine_factory(user=user, name="Riesling", vintage=None)
    assert str(wine) == "Riesling"


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
