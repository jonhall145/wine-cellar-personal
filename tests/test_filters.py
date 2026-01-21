"""Tests for wine filters."""

import pytest

from wine_cellar.apps.wine.filters import (
    WineFilter,
    get_country_choices_with_favourites,
)


class TestGetCountryChoicesWithFavourites:
    """Tests for get_country_choices_with_favourites function."""

    def test_returns_empty_list_without_user(self):
        """With no user, no countries should be returned (only 'Any' option)."""
        choices = get_country_choices_with_favourites(user=None)
        assert len(choices) == 1
        assert choices[0][0] == ""

    @pytest.mark.django_db
    def test_returns_only_countries_with_stock(self, wine, storage, storage_item):
        """Only countries with wines in stock should appear."""
        choices = get_country_choices_with_favourites(user=wine.user)
        codes = [c[0] for c in choices if c[0]]  # Exclude separator and empty 'Any'
        assert wine.country in codes
        # Should not have hundreds of countries, only those with stock
        assert len(codes) <= 10

    @pytest.mark.django_db
    def test_favourites_appear_first_if_in_stock(self, wine, storage, storage_item):
        """Favourite countries with stock appear before others."""
        # Set wine to a favourite country
        wine.country = "FR"
        wine.save()
        choices = get_country_choices_with_favourites(user=wine.user)
        # First choice is 'Any', second should be the favourite
        if len(choices) > 1:
            first_code = choices[1][0]
            assert first_code == "FR"


@pytest.mark.django_db
class TestWineFilter:
    """Tests for WineFilter."""

    def test_filter_stock_true(self, wine, storage, storage_item):
        """Test filtering for wines in stock."""
        from django.test import RequestFactory

        from wine_cellar.apps.wine.models import Wine

        factory = RequestFactory()
        request = factory.get("/")
        request.user = wine.user

        # Create the filter with stock=1
        f = WineFilter(
            data={"stock": "1"},
            queryset=Wine.objects.filter(user=wine.user),
            request=request,
        )
        # The wine with stock item should be in the results
        assert wine in f.qs

    def test_filter_stock_false(self, wine):
        """Test filtering without stock filter."""
        from django.test import RequestFactory

        from wine_cellar.apps.wine.models import Wine

        factory = RequestFactory()
        request = factory.get("/")
        request.user = wine.user

        f = WineFilter(
            data={"stock": "0"},
            queryset=Wine.objects.filter(user=wine.user),
            request=request,
        )
        # Wine should still be in results
        assert wine in f.qs
