import json

import pytest
from django.test import RequestFactory
from django.utils import timezone

from wine_cellar.apps.storage.models import StorageItem
from wine_cellar.apps.wine.filters import (
    WineFilter,
    get_appellation_choices,
    get_grape_queryset,
)
from wine_cellar.apps.wine.models import Appellation, Grape, Wine, WineType


@pytest.mark.django_db
def test_get_appellation_choices_with_missing(user, wine_factory, storage_item_factory):
    appellation, _ = Appellation.objects.get_or_create(
        name="Napa Valley",
        country="US",
        defaults={"latitude": 38.3, "longitude": -122.3},
    )
    wine = wine_factory(user=user, appellation=appellation)
    storage_item_factory(wine=wine, user=user)

    choices = get_appellation_choices(user=user)

    assert choices[0][0] == ""
    assert choices[1][0] == "missing"
    assert appellation.pk in [choice[0] for choice in choices]


@pytest.mark.django_db
def test_filter_ready_to_drink_includes_current(user, wine_factory):
    request = RequestFactory().get("/")
    request.user = user

    wine_ready = wine_factory(user=user, drink_from=0, drink_to=None)
    wine_future = wine_factory(user=user, drink_from=3000, drink_to=None)

    filt = WineFilter(
        data={"ready_to_drink": "1", "stock": "0", "order": "created"},
        queryset=Wine.objects.filter(user=user),
        request=request,
    )

    assert wine_ready in filt.qs
    assert wine_future not in filt.qs


@pytest.mark.django_db
def test_filter_has_window(user, wine_factory):
    request = RequestFactory().get("/")
    request.user = user

    wine_window = wine_factory(user=user, drink_from=2025, drink_to=2030)
    wine_no_window = wine_factory(user=user, drink_from=None, drink_to=None)

    filt = WineFilter(
        data={"has_window": "1", "stock": "0", "order": "created"},
        queryset=Wine.objects.filter(user=user),
        request=request,
    )

    assert wine_window in filt.qs
    assert wine_no_window not in filt.qs


@pytest.mark.django_db
def test_filter_rating_supports_multiple_selected_ratings(user, wine_factory):
    request = RequestFactory().get("/")
    request.user = user

    zero_star = wine_factory(user=user, rating=0)
    one_star = wine_factory(user=user, rating=1)
    two_star = wine_factory(user=user, rating=2)
    unrated = wine_factory(user=user, rating=None)

    filt = WineFilter(
        data={"rating": ["0", "1"], "stock": "0", "order": "created"},
        queryset=Wine.objects.filter(user=user),
        request=request,
    )

    assert zero_star in filt.qs
    assert one_star in filt.qs
    assert unrated in filt.qs
    assert two_star not in filt.qs


@pytest.mark.django_db
def test_filter_order_created_annotates_stock_date_for_direct_use(
    user, wine_factory, storage_item_factory
):
    request = RequestFactory().get("/")
    request.user = user

    older = wine_factory(user=user, name="Older")
    newer = wine_factory(user=user, name="Newer")
    older_item = storage_item_factory(wine=older, user=user)
    newer_item = storage_item_factory(wine=newer, user=user)
    old_created = timezone.now() - timezone.timedelta(days=20)
    new_created = timezone.now() - timezone.timedelta(days=3)
    StorageItem.objects.filter(pk=older_item.pk).update(created=old_created)
    StorageItem.objects.filter(pk=newer_item.pk).update(created=new_created)

    filt = WineFilter(
        data={"stock": "0", "order": "created"},
        queryset=Wine.objects.filter(user=user),
        request=request,
    )

    assert list(filt.qs) == [older, newer]


@pytest.mark.django_db
def test_get_grape_queryset_prioritises_selected_wine_type(
    user, wine_factory, storage_item_factory
):
    red_grape = Grape.objects.create(
        name="Alpha Red",
        user=user,
        household=user.user_settings.active_household,
    )
    white_grape = Grape.objects.create(
        name="Beta White",
        user=user,
        household=user.user_settings.active_household,
    )
    unused_grape = Grape.objects.create(
        name="Zulu Unused",
        user=user,
        household=user.user_settings.active_household,
    )

    red_wine = wine_factory(user=user, wine_type=WineType.RED, grapes=[red_grape])
    white_wine = wine_factory(user=user, wine_type=WineType.WHITE, grapes=[white_grape])
    storage_item_factory(wine=red_wine, user=user)
    storage_item_factory(wine=white_wine, user=user)

    grapes = list(
        get_grape_queryset(user, selected_wine_types=[WineType.RED]).values_list(
            "name", flat=True
        )
    )

    assert grapes == ["Alpha Red", "Beta White", "Zulu Unused"]
    assert unused_grape.name == "Zulu Unused"


@pytest.mark.django_db
def test_filter_grapes_matches_any_selected_grape(user, wine_factory):
    request = RequestFactory().get("/")
    request.user = user

    merlot = Grape.objects.create(
        name="Merlot",
        user=user,
        household=user.user_settings.active_household,
    )
    riesling = Grape.objects.create(
        name="Riesling",
        user=user,
        household=user.user_settings.active_household,
    )
    chardonnay = Grape.objects.create(
        name="Chardonnay",
        user=user,
        household=user.user_settings.active_household,
    )

    merlot_wine = wine_factory(user=user, grapes=[merlot])
    riesling_wine = wine_factory(user=user, grapes=[riesling])
    other_wine = wine_factory(user=user, grapes=[chardonnay])

    filt = WineFilter(
        data={
            "grapes": [str(merlot.pk), str(riesling.pk)],
            "stock": "0",
            "order": "created",
        },
        queryset=Wine.objects.filter(user=user),
        request=request,
    )

    assert {wine.pk for wine in filt.qs} == {merlot_wine.pk, riesling_wine.pk}
    assert other_wine not in filt.qs


@pytest.mark.django_db
def test_filter_form_grapes_include_wine_type_metadata(
    user, wine_factory, storage_item_factory
):
    request = RequestFactory().get("/")
    request.user = user

    merlot = Grape.objects.create(
        name="Merlot",
        user=user,
        household=user.user_settings.active_household,
    )
    white_grape = Grape.objects.create(
        name="Riesling",
        user=user,
        household=user.user_settings.active_household,
    )
    red_wine = wine_factory(user=user, wine_type=WineType.RED, grapes=[merlot])
    white_wine = wine_factory(user=user, wine_type=WineType.WHITE, grapes=[white_grape])
    storage_item_factory(wine=red_wine, user=user)
    storage_item_factory(wine=white_wine, user=user)

    filt = WineFilter(
        data={"wine_type": [WineType.RED], "stock": "1", "order": "created"},
        queryset=Wine.objects.filter(user=user),
        request=request,
    )

    grape_field = filt.form.fields["grapes"]
    grape_config = json.loads(grape_field.widget.attrs["data-tom_config"])
    grape_type_map = json.loads(grape_field.widget.attrs["data-grape-wine-types"])

    assert list(grape_field.queryset.values_list("name", flat=True))[:2] == [
        "Merlot",
        "Riesling",
    ]
    assert grape_config["maxOptions"] is None
    assert grape_type_map[str(merlot.pk)] == [WineType.RED]
    assert grape_type_map[str(white_grape.pk)] == [WineType.WHITE]
