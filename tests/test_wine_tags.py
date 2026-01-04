"""Tests for wine template tags."""
from datetime import date
from unittest.mock import patch

from wine_cellar.apps.wine.templatetags.wine_tags import (
    drink_window_indicator,
    rating_stars,
    wine_type_badge,
)


class TestWineTypeBadge:
    """Tests for wine_type_badge template tag."""

    def test_empty_wine_type_returns_empty_string(self):
        assert wine_type_badge("") == ""
        assert wine_type_badge(None) == ""

    def test_known_wine_type_returns_styled_badge(self):
        result = wine_type_badge("RE")
        assert 'wine-type-badge--red' in result
        assert 'Red' in result

    def test_white_wine_type(self):
        result = wine_type_badge("WH")
        assert 'wine-type-badge--white' in result

    def test_unknown_wine_type_returns_basic_badge(self):
        result = wine_type_badge("XX")
        assert 'wine-type-badge' in result
        assert 'wine-type-badge--' not in result
        assert 'XX' in result


class TestRatingStars:
    """Tests for rating_stars template tag."""

    def test_none_rating_returns_empty_indicator(self):
        result = rating_stars(None)
        assert 'rating-stars--empty' in result
        assert '—' in result

    def test_full_rating_shows_all_filled_stars(self):
        result = rating_stars(10)  # 10/10 = 5 full stars
        assert result.count('fa-star rating-stars__star') == 5
        assert 'star-half' not in result

    def test_half_rating_shows_half_star(self):
        result = rating_stars(5)  # 5/10 = 2.5 stars (2 full + 1 half)
        assert 'star-half-stroke' in result

    def test_low_rating_shows_empty_stars(self):
        result = rating_stars(2)  # 2/10 = 1 star
        assert 'fa-regular fa-star' in result

    def test_zero_rating(self):
        result = rating_stars(0)
        # 0/10 = 0 stars, all empty
        assert 'rating-stars__star--filled' not in result


class TestDrinkWindowIndicator:
    """Tests for drink_window_indicator template tag."""

    def test_missing_vintage_returns_empty(self):
        assert drink_window_indicator(None, 2025) == ""

    def test_missing_drink_by_returns_empty(self):
        assert drink_window_indicator(2020, None) == ""

    def test_invalid_drink_by_returns_empty(self):
        assert drink_window_indicator(2020, "invalid") == ""

    @patch('wine_cellar.apps.wine.templatetags.wine_tags.date')
    def test_wine_too_young(self, mock_date):
        mock_date.today.return_value = date(2020, 1, 1)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
        result = drink_window_indicator(2018, 2030)
        assert 'drink-window--young' in result
        assert 'hourglass' in result

    @patch('wine_cellar.apps.wine.templatetags.wine_tags.date')
    def test_wine_ready_to_drink(self, mock_date):
        mock_date.today.return_value = date(2028, 1, 1)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
        result = drink_window_indicator(2018, 2030)
        assert 'drink-window--ready' in result
        assert 'Ready' in result

    @patch('wine_cellar.apps.wine.templatetags.wine_tags.date')
    def test_wine_past_prime(self, mock_date):
        mock_date.today.return_value = date(2035, 1, 1)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
        result = drink_window_indicator(2018, 2030)
        assert 'drink-window--prime' in result
        assert 'Past prime' in result
