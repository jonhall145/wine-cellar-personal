"""Tests for wine filters."""
import pytest

from wine_cellar.apps.wine.filters import (
    WineFilter,
    get_country_choices_with_favourites,
)


class TestGetCountryChoicesWithFavourites:
    """Tests for get_country_choices_with_favourites function."""

    def test_returns_list_with_favourites_first(self):
        choices = get_country_choices_with_favourites(user=None)
        # Should have favourites at the top
        assert len(choices) > 10
        # GB, PT, FR should be in the first few
        first_codes = [c[0] for c in choices[:5]]
        assert "GB" in first_codes
        assert "PT" in first_codes
        assert "FR" in first_codes

    def test_includes_separator(self):
        choices = get_country_choices_with_favourites(user=None)
        # Should have a separator (empty code with dashes)
        separators = [c for c in choices if c[0] == "" and "─" in c[1]]
        assert len(separators) == 1


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
