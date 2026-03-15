"""Tests for grape name normalization."""

from wine_cellar.apps.wine.services.grape_normalization import (
    normalize_grape_list,
    normalize_grape_name,
)


class TestNormalizeGrapeName:
    def test_simple_name_preserved(self):
        assert normalize_grape_name("Cabernet Sauvignon") == "Cabernet Sauvignon"

    def test_strips_whitespace(self):
        assert normalize_grape_name("  Merlot  ") == "Merlot"

    def test_title_cases_lowercase(self):
        assert normalize_grape_name("pinot noir") == "Pinot Noir"

    def test_title_cases_uppercase(self):
        assert normalize_grape_name("RIESLING") == "Riesling"

    def test_preserves_mixed_case(self):
        assert normalize_grape_name("Grüner Veltliner") == "Grüner Veltliner"

    def test_removes_parenthetical(self):
        assert normalize_grape_name("Muskat (Muskateller)") == "Muskateller"

    def test_removes_parenthetical_with_long_note(self):
        assert (
            normalize_grape_name("Pinot (specific variety not specified)") is None
        )  # "Pinot" is in skip list

    def test_alias_shiraz_to_syrah(self):
        assert normalize_grape_name("Shiraz") == "Syrah"

    def test_alias_tinta_roriz_to_tempranillo(self):
        assert normalize_grape_name("Tinta Roriz") == "Tempranillo"

    def test_alias_garnacha_to_grenache(self):
        assert normalize_grape_name("Garnacha") == "Grenache"

    def test_alias_primitivo_to_zinfandel(self):
        assert normalize_grape_name("Primitivo") == "Zinfandel"

    def test_alias_pinot_grigio_to_pinot_gris(self):
        assert normalize_grape_name("Pinot Grigio") == "Pinot Gris"

    def test_alias_brunello_to_sangiovese(self):
        assert normalize_grape_name("Brunello") == "Sangiovese"

    def test_alias_pinot_bianco_to_pinot_blanc(self):
        assert normalize_grape_name("Pinot Bianco") == "Pinot Blanc"

    def test_alias_pinot_nero_to_pinot_noir(self):
        assert normalize_grape_name("Pinot Nero") == "Pinot Noir"

    def test_alias_case_insensitive(self):
        assert normalize_grape_name("SHIRAZ") == "Syrah"
        assert normalize_grape_name("tinta roriz") == "Tempranillo"

    def test_skip_not_found(self):
        assert normalize_grape_name("not found") is None

    def test_skip_unknown(self):
        assert normalize_grape_name("unknown") is None

    def test_skip_blend(self):
        assert normalize_grape_name("blend") is None

    def test_skip_empty(self):
        assert normalize_grape_name("") is None
        assert normalize_grape_name("   ") is None

    def test_skip_bare_pinot(self):
        assert normalize_grape_name("Pinot") is None

    def test_skip_na(self):
        assert normalize_grape_name("n/a") is None
        assert normalize_grape_name("none") is None


class TestNormalizeGrapeList:
    def test_basic_list(self):
        result = normalize_grape_list(["Merlot", "Cabernet Sauvignon"])
        assert result == ["Merlot", "Cabernet Sauvignon"]

    def test_deduplicates(self):
        result = normalize_grape_list(["Merlot", "merlot", "MERLOT"])
        assert result == ["Merlot"]

    def test_deduplicates_aliases(self):
        result = normalize_grape_list(["Tinta Roriz", "Tempranillo"])
        assert result == ["Tempranillo"]

    def test_filters_invalid(self):
        result = normalize_grape_list(["Merlot", "not found", "", "Syrah"])
        assert result == ["Merlot", "Syrah"]

    def test_preserves_order(self):
        result = normalize_grape_list(["Syrah", "Grenache", "Mourvèdre"])
        assert result == ["Syrah", "Grenache", "Mourvèdre"]

    def test_empty_list(self):
        assert normalize_grape_list([]) == []

    def test_all_invalid(self):
        assert normalize_grape_list(["not found", "unknown", ""]) == []
