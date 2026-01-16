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
        assert "wine-type-badge--red" in result
        assert "Red" in result

    def test_white_wine_type(self):
        result = wine_type_badge("WH")
        assert "wine-type-badge--white" in result

    def test_unknown_wine_type_returns_basic_badge(self):
        result = wine_type_badge("XX")
        assert "wine-type-badge" in result
        assert "wine-type-badge--" not in result
        assert "XX" in result


class TestRatingStars:
    """Tests for rating_stars template tag (0-3 star scale)."""

    def test_none_rating_returns_empty_indicator(self):
        result = rating_stars(None)
        assert "rating-stars--empty" in result
        assert "—" in result

    def test_full_rating_shows_all_filled_stars(self):
        result = rating_stars(3)  # 3/3 = 3 full stars
        assert result.count("fa-star rating-stars__star") == 3
        assert "star-half" not in result

    def test_partial_rating_shows_correct_stars(self):
        result = rating_stars(2)  # 2/3 = 2 full stars, 1 empty
        assert result.count("rating-stars__star--filled") == 2
        assert "fa-regular fa-star" in result

    def test_low_rating_shows_empty_stars(self):
        result = rating_stars(1)  # 1/3 = 1 filled, 2 empty
        assert result.count("rating-stars__star--filled") == 1
        assert "fa-regular fa-star" in result

    def test_zero_rating(self):
        result = rating_stars(0)
        # 0/3 = 0 stars, all empty
        assert "rating-stars__star--filled" not in result
        assert result.count("fa-regular fa-star") == 3


class TestDrinkWindowIndicator:
    """Tests for drink_window_indicator template tag."""

    def test_both_none_returns_empty(self):
        assert drink_window_indicator(None, None) == ""

    def test_only_drink_to_set_ready(self):
        """If only drink_to is set, assume ready now if within window."""
        result = drink_window_indicator(None, 2030)
        assert "drink-window--ready" in result

    def test_only_drink_from_set_future(self):
        """If only drink_from is set and in future, shows young."""
        result = drink_window_indicator(2050, None)
        assert "drink-window--young" in result

    @patch("wine_cellar.apps.wine.templatetags.wine_tags.date")
    def test_wine_too_young(self, mock_date):
        mock_date.today.return_value = date(2020, 1, 1)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
        # drink_from=2027, drink_to=2030, current year 2020 -> too young
        result = drink_window_indicator(2027, 2030)
        assert "drink-window--young" in result
        assert "hourglass" in result

    @patch("wine_cellar.apps.wine.templatetags.wine_tags.date")
    def test_wine_ready_to_drink(self, mock_date):
        mock_date.today.return_value = date(2028, 1, 1)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
        # drink_from=2027, drink_to=2030, current year 2028 -> ready
        result = drink_window_indicator(2027, 2030)
        assert "drink-window--ready" in result
        assert "Ready" in result

    @patch("wine_cellar.apps.wine.templatetags.wine_tags.date")
    def test_wine_past_prime(self, mock_date):
        mock_date.today.return_value = date(2035, 1, 1)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
        # drink_from=2027, drink_to=2030, current year 2035 -> past prime
        result = drink_window_indicator(2027, 2030)
        assert "drink-window--prime" in result
        assert "Past prime" in result

    @patch("wine_cellar.apps.wine.templatetags.wine_tags.date")
    def test_now_value_drink_from(self, mock_date):
        """Test that 0 (now) is handled correctly for drink_from."""
        mock_date.today.return_value = date(2026, 1, 1)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
        # drink_from=0 (now=2026), drink_to=2030 -> ready
        result = drink_window_indicator(0, 2030)
        assert "drink-window--ready" in result

    @patch("wine_cellar.apps.wine.templatetags.wine_tags.date")
    def test_now_value_drink_to(self, mock_date):
        """Test that 0 (now) is handled correctly for drink_to."""
        mock_date.today.return_value = date(2026, 1, 1)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
        # drink_from=2020, drink_to=0 (now=2026) -> ready (current year == end)
        result = drink_window_indicator(2020, 0)
        assert "drink-window--ready" in result
