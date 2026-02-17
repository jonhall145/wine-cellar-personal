import pytest
from django.test import RequestFactory

from wine_cellar.apps.wine.filters import (
    WineFilter,
    get_appellation_choices,
)
from wine_cellar.apps.wine.models import Appellation, Wine


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
        data={"ready_to_drink": "1"},
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
        data={"has_window": "1"},
        queryset=Wine.objects.filter(user=user),
        request=request,
    )

    assert wine_window in filt.qs
    assert wine_no_window not in filt.qs
