"""Tests for whisky template tags."""

from wine_cellar.apps.whisky.templatetags.whisky_tags import (
    fill_level_display,
    peated_badge,
    whisky_type_badge,
)


class TestWhiskyTypeBadge:
    """Tests for whisky_type_badge template tag."""

    def test_empty_whisky_type_returns_empty_string(self):
        assert whisky_type_badge("") == ""
        assert whisky_type_badge(None) == ""

    def test_known_whisky_type_returns_styled_badge(self):
        result = whisky_type_badge("SM")
        assert "whisky-type-badge--single-malt" in result
        assert "Single Malt" in result

    def test_blended_malt_type(self):
        result = whisky_type_badge("BM")
        assert "whisky-type-badge--blended-malt" in result

    def test_unknown_whisky_type_returns_escaped_badge(self):
        """Fallback case should escape label and wrap in mark_safe."""
        result = whisky_type_badge("XX")
        assert "whisky-type-badge" in result
        assert "whisky-type-badge--" not in result
        assert "XX" in result

    def test_xss_protection_in_fallback(self):
        """Test that malicious input is escaped in fallback branch."""
        result = whisky_type_badge("<script>alert('xss')</script>")
        # Should escape the HTML tags
        assert "&lt;script&gt;" in result
        assert "<script>" not in result


class TestPeatedBadge:
    """Tests for peated_badge template tag."""

    def test_empty_peated_level_returns_empty_string(self):
        assert peated_badge("") == ""
        assert peated_badge(None) == ""

    def test_known_peated_level_returns_styled_badge(self):
        result = peated_badge("PE")
        assert "peated-badge--peated" in result
        assert "Peated" in result

    def test_unpeated_level(self):
        result = peated_badge("UP")
        assert "peated-badge--unpeated" in result

    def test_unknown_peated_level_returns_escaped_badge(self):
        """Fallback case should escape label and wrap in mark_safe."""
        result = peated_badge("XX")
        assert "peated-badge" in result
        assert "peated-badge--" not in result
        assert "XX" in result

    def test_xss_protection_in_fallback(self):
        """Test that malicious input is escaped in fallback branch."""
        result = peated_badge("<script>alert('xss')</script>")
        # Should escape the HTML tags
        assert "&lt;script&gt;" in result
        assert "<script>" not in result


class TestFillLevelDisplay:
    """Tests for fill_level_display template tag."""

    def test_empty_fill_level_returns_empty_string(self):
        assert fill_level_display("") == ""
        assert fill_level_display(None) == ""

    def test_known_fill_level_returns_styled_display(self):
        result = fill_level_display("UN")
        assert "fill-level--unopened" in result
        assert "Unopened" in result
        assert "fa-battery-full" in result

    def test_opened_fill_level(self):
        result = fill_level_display("OP")
        assert "fill-level--opened" in result
        assert "fa-battery-half" in result

    def test_unknown_fill_level_returns_escaped_display(self):
        """Fallback case should escape label and icon_class and wrap in mark_safe."""
        result = fill_level_display("XX")
        assert "fill-level" in result
        assert "fill-level--" not in result
        assert "XX" in result

    def test_xss_protection_in_fallback(self):
        """Test that malicious input is escaped in fallback branch."""
        result = fill_level_display("<script>alert('xss')</script>")
        # Should escape the HTML tags
        assert "&lt;script&gt;" in result
        assert "<script>" not in result
