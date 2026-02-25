"""Tests for whisky template tags."""

from types import SimpleNamespace

from wine_cellar.apps.whisky.templatetags.whisky_tags import (
    cask_border_css,
    classify_cask_type,
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


class TestClassifyCaskType:
    """Tests for cask type classification logic."""

    def test_empty_returns_other(self):
        assert classify_cask_type("") == "other"
        assert classify_cask_type(None) == "other"

    def test_bourbon(self):
        assert classify_cask_type("Bourbon") == "bourbon"

    def test_first_fill_bourbon(self):
        assert classify_cask_type("First Fill Bourbon") == "bourbon"

    def test_virgin_oak(self):
        assert classify_cask_type("Virgin Oak") == "bourbon"

    def test_american_oak(self):
        assert classify_cask_type("American Oak") == "bourbon"

    def test_french_oak(self):
        assert classify_cask_type("French Oak") == "bourbon"

    def test_sherry_oloroso(self):
        assert classify_cask_type("Sherry (Oloroso)") == "sherry"

    def test_sherry_px(self):
        assert classify_cask_type("Pedro Ximénez") == "sherry"

    def test_px_abbreviation(self):
        assert classify_cask_type("PX") == "sherry"

    def test_port(self):
        assert classify_cask_type("Port") == "sherry"

    def test_fino(self):
        assert classify_cask_type("Fino") == "sherry"

    def test_mixed_bourbon_sherry_prioritizes_sherry(self):
        assert classify_cask_type("Bourbon, Sherry (Oloroso)") == "sherry"

    def test_rum_returns_other(self):
        assert classify_cask_type("Rum") == "other"

    def test_case_insensitive(self):
        assert classify_cask_type("BOURBON") == "bourbon"
        assert classify_cask_type("sherry") == "sherry"


class TestCaskBorderCss:
    """Tests for cask_border_css template filter."""

    def test_bourbon_non_cs(self):
        whisky = SimpleNamespace(cask_type="Bourbon", cask_strength=False)
        assert cask_border_css(whisky) == "cask-bourbon"

    def test_bourbon_cs(self):
        whisky = SimpleNamespace(cask_type="Bourbon", cask_strength=True)
        assert cask_border_css(whisky) == "cask-bourbon-cs"

    def test_sherry_non_cs(self):
        whisky = SimpleNamespace(cask_type="Sherry (Oloroso)", cask_strength=False)
        assert cask_border_css(whisky) == "cask-sherry"

    def test_sherry_cs(self):
        whisky = SimpleNamespace(cask_type="Sherry (Oloroso)", cask_strength=True)
        assert cask_border_css(whisky) == "cask-sherry-cs"

    def test_other_non_cs(self):
        whisky = SimpleNamespace(cask_type="Rum", cask_strength=False)
        assert cask_border_css(whisky) == "cask-other"

    def test_other_cs(self):
        whisky = SimpleNamespace(cask_type="Rum", cask_strength=True)
        assert cask_border_css(whisky) == "cask-other-cs"

    def test_empty_cask_type(self):
        whisky = SimpleNamespace(cask_type="", cask_strength=False)
        assert cask_border_css(whisky) == "cask-other"

    def test_missing_attributes_default(self):
        whisky = SimpleNamespace()
        assert cask_border_css(whisky) == "cask-other"
