import base64
import io

from PIL import Image

from wine_cellar.apps.wine.services.vision_extraction import (
    WineVisionExtractor,
    resize_image_for_api,
)


def _make_image_bytes(width=2000, height=2000, mode="RGB"):
    img = Image.new(mode, (width, height), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def test_resize_image_for_api_downsizes_large_image():
    original = _make_image_bytes()
    resized = resize_image_for_api(original)
    assert resized
    assert resized != original


def test_resize_image_for_api_keeps_small_image():
    small = _make_image_bytes(width=400, height=400)
    assert resize_image_for_api(small) == small


def test_process_field_value_maps_type_and_vintage():
    extractor = WineVisionExtractor()
    assert extractor._process_field_value("wine_type", "Red wine") == "RE"
    assert extractor._process_field_value("vintage", "Vintage 2018") == 2018


def test_parse_claude_response_builds_data_and_confidence():
    extractor = WineVisionExtractor()
    response = """
NAME: Test Wine
TYPE: red
VINTAGE: 2020
COUNTRY: France
CONFIDENCE: high
FIELD_CONFIDENCE: name=high, type=high, vintage=medium, country=low
"""
    parsed = extractor._parse_claude_response(response)
    assert parsed["data"]["name"] == "Test Wine"
    assert parsed["data"]["wine_type"] == "RE"
    assert parsed["data"]["vintage"] == 2020
    assert parsed["data"]["country"] == "FR"
    assert parsed["confidence"] == "high"
    assert parsed["field_confidence"]["name"] == "high"
    assert parsed["field_confidence"]["vintage"] == "medium"
    assert parsed["field_confidence"]["country"] == "low"


def test_parse_claude_response_without_field_confidence():
    extractor = WineVisionExtractor()
    response = """
NAME: Test Wine
CONFIDENCE: medium
"""
    parsed = extractor._parse_claude_response(response)
    assert parsed["field_confidence"] == {}


def test_fallback_regex_extraction_extracts_volume_and_abv():
    extractor = WineVisionExtractor()
    result = extractor._fallback_regex_extraction("13.5% ABV 750ml")
    assert result["data"]["abv"] == 13.5
    assert result["data"]["size"] == "ST"
