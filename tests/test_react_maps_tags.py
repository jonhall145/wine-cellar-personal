"""Tests for react_maps_tags template tags."""

import json
from html.parser import HTMLParser

import pytest

from wine_cellar.apps.wine.templatetags.react_maps_tags import react_map, wine_to_json


@pytest.mark.django_db
class TestWineToJson:
    """Tests for wine_to_json helper function."""

    def test_wine_to_json_returns_expected_keys(self, wine):
        result = wine_to_json(wine)
        assert "name" in result
        assert "country" in result
        assert "country_name" in result
        assert "country_icon" in result
        assert "image" in result
        assert "vintage" in result
        assert "url" in result

    def test_wine_to_json_values(self, wine):
        result = wine_to_json(wine)
        assert result["name"] == wine.name
        assert result["country"] == wine.country
        assert result["url"] == wine.get_absolute_url()


@pytest.mark.django_db
class TestReactMap:
    """Tests for react_map template tag."""

    def test_react_map_returns_div_with_data(self, wine):
        result = react_map([wine])
        assert '<div id="wine_map"' in result
        assert "data-attributes" in result

    def test_react_map_empty_wines_list(self):
        result = react_map([])
        assert '<div id="wine_map"' in result

    def test_react_map_data_structure(self, wine):
        result = react_map([wine])
        attributes = {}

        class DataAttributesParser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                attributes.update(attrs)

        DataAttributesParser().feed(str(result))
        data = json.loads(attributes["data-attributes"])

        assert "OpenFreeMap" in data["map"]["attribution"]
        assert data["wines"][0]["name"] == wine.name
