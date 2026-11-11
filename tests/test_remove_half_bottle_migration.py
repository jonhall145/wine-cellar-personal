from importlib import import_module

import pytest
from django.apps import apps

from wine_cellar.apps.storage.models import BottleMoveHistory, StorageItem
from wine_cellar.apps.wine.models import (
    BottleNote,
    DrinkRecord,
    PriceHistory,
    Size,
    Wine,
)

replace_half_bottle_sizes = import_module(
    "wine_cellar.apps.wine.migrations.0053_remove_half_bottle_size"
).replace_half_bottle_sizes


@pytest.mark.django_db
def test_half_sizes_keep_household_ownership_and_use_global_sizes_when_global(
    user, household_factory, wine_factory
):
    household_a = user.user_settings.active_household
    household_b = household_factory()
    household_standard = Size.objects.create(
        name="ST",
        user=user,
        household=household_a,
    )
    household_half = Size.objects.create(
        name="HA",
        user=user,
        household=household_b,
    )
    global_standard = Size.objects.create(name="ST")
    global_half = Size.objects.create(name="HA")
    household_wine = wine_factory(
        user=user,
        household=household_b,
        name="Household B wine",
        size=household_half,
    )
    global_wine = wine_factory(
        user=user,
        household=household_a,
        name="Global size wine",
        size=global_half,
    )

    replace_half_bottle_sizes(apps, None)

    household_half.refresh_from_db()
    household_standard.refresh_from_db()
    household_wine.refresh_from_db()
    global_wine.refresh_from_db()

    assert household_half.name == "ST"
    assert household_half.household_id == household_b.pk
    assert household_half.user_id is None
    assert household_standard.household_id == household_a.pk
    assert household_wine.size_id == household_half.pk
    global_wine.size.refresh_from_db()
    assert global_wine.size.name == global_standard.name
    assert global_wine.size.household_id is None
    assert global_wine.size.user_id is None


@pytest.mark.django_db
def test_size_migration_merges_colliding_wines_without_losing_inventory_or_history(
    user,
    wine_factory,
    storage_factory,
    storage_item_factory,
):
    household = user.user_settings.active_household
    standard_size = Size.objects.create(
        user=user,
        household=household,
        name="ST",
    )
    half_size = Size.objects.create(
        user=user,
        household=household,
        name="HA",
    )
    identity = {
        "user": user,
        "household": household,
        "name": "Same wine, different bottle size",
        "wine_type": "RE",
        "abv": 12.5,
        "vintage": 2019,
        "country": "FR",
    }
    standard_wine = wine_factory(size=standard_size, **identity)
    half_wine = wine_factory(size=half_size, **identity)
    half_wine.category = "DR"
    half_wine.drink_by = "2028-01-01"
    half_wine.drink_from = 2024
    half_wine.drink_to = 2028
    half_wine.comment = "Half-size cellar note"
    half_wine.rating = 2
    half_wine.subregion = "Left Bank"
    half_wine.price = "25.00"
    half_wine.price_url = "https://example.com/wine"
    half_wine.save()
    storage = storage_factory(user=user, household=household)
    item = storage_item_factory(
        user=user,
        household=household,
        wine=half_wine,
        storage=storage,
    )
    BottleNote.objects.create(
        user=user,
        household=household,
        storage_item=item,
        note_date="2024-01-02",
        note="Still improving",
    )
    DrinkRecord.objects.create(
        user=user,
        household=household,
        wine=half_wine,
        storage_item=item,
        date_consumed="2024-02-03",
        tasting_notes="Balanced",
    )
    PriceHistory.objects.create(
        user=user,
        household=household,
        wine=half_wine,
        price="25.00",
    )
    move = BottleMoveHistory.objects.create(
        user=user,
        storage_item=item,
        from_storage=storage,
        to_storage=storage,
        from_row=1,
        from_column=1,
        to_row=2,
        to_column=2,
    )

    replace_half_bottle_sizes(apps, None)

    assert (
        Wine.objects.filter(
            user=user,
            name=identity["name"],
            deleted=False,
        ).count()
        == 1
    )
    assert StorageItem.objects.filter(pk=item.pk, wine=standard_wine).exists()
    assert BottleNote.objects.filter(
        storage_item=item,
        note="Still improving",
    ).exists()
    assert DrinkRecord.objects.filter(
        wine=standard_wine,
        storage_item=item,
        tasting_notes="Balanced",
    ).exists()
    assert PriceHistory.objects.filter(
        wine=standard_wine,
        price="25.00",
    ).exists()
    assert BottleMoveHistory.objects.filter(pk=move.pk, storage_item=item).exists()
    standard_wine.refresh_from_db()
    assert standard_wine.category == "DR"
    assert str(standard_wine.drink_by) == "2028-01-01"
    assert standard_wine.drink_from == 2024
    assert standard_wine.drink_to == 2028
    assert standard_wine.comment == "Half-size cellar note"
    assert standard_wine.rating == 2
    assert standard_wine.subregion == "Left Bank"
    assert str(standard_wine.price) == "25.00"
    assert standard_wine.price_url == "https://example.com/wine"


@pytest.mark.django_db
def test_size_migration_keeps_standard_metadata_on_conflict(user, wine_factory):
    household = user.user_settings.active_household
    standard_size = Size.objects.create(user=user, household=household, name="ST")
    half_size = Size.objects.create(user=user, household=household, name="HA")
    identity = {
        "user": user,
        "household": household,
        "name": "Conflicting wine metadata",
        "wine_type": "RE",
        "abv": 12.5,
        "vintage": 2019,
        "country": "FR",
    }
    standard_wine = wine_factory(
        size=standard_size,
        comment="Standard comment",
        rating=3,
        **identity,
    )
    half_wine = wine_factory(
        size=half_size,
        comment="Half-size comment",
        rating=1,
        **identity,
    )

    replace_half_bottle_sizes(apps, None)

    standard_wine.refresh_from_db()
    assert standard_wine.comment == "Standard comment"
    assert standard_wine.rating == 3
    assert not Wine.objects.filter(pk=half_wine.pk).exists()


@pytest.mark.django_db
def test_size_migration_does_not_merge_matching_wines_across_households(
    user, household_factory, wine_factory
):
    first_household = user.user_settings.active_household
    second_household = household_factory()
    standard_size = Size.objects.filter(name="ST", user=None, household=None).order_by(
        "pk"
    ).first() or Size.objects.create(name="ST")
    half_size = Size.objects.create(name="HA")
    identity = {
        "user": user,
        "name": "Same wine in separate households",
        "wine_type": "RE",
        "abv": 12.5,
        "vintage": 2019,
        "country": "FR",
    }
    standard_wine = wine_factory(
        household=first_household,
        size=standard_size,
        **identity,
    )
    half_wine = wine_factory(
        household=second_household,
        size=half_size,
        **identity,
    )

    replace_half_bottle_sizes(apps, None)

    standard_wine.refresh_from_db()
    half_wine.refresh_from_db()
    assert standard_wine.pk != half_wine.pk
    assert standard_wine.household_id == first_household.pk
    assert half_wine.household_id == second_household.pk
    assert half_wine.size_id != standard_wine.size_id
    assert half_wine.size.name == "ST"
    assert half_wine.size.household_id == second_household.pk
