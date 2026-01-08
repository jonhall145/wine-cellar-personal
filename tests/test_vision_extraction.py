"""Tests for vision extraction AJAX endpoint with barcode-first workflow."""

import base64
import io
import json
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from PIL import Image


def create_test_image_file():
    """Create a simple test image as bytes."""
    img = Image.new("RGB", (100, 100), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer


class TestExtractWineVisionAjax:
    """Tests for the extract_wine_vision_ajax view."""

    @pytest.mark.django_db
    def test_requires_authentication(self, client):
        """Test that the endpoint requires authentication."""
        url = reverse("wine-extract-vision")
        response = client.post(url)
        # Should redirect to login
        assert response.status_code == HTTPStatus.FOUND

    @pytest.mark.django_db
    def test_requires_post_method(self, client, user):
        """Test that GET requests are rejected."""
        client.force_login(user)
        url = reverse("wine-extract-vision")
        response = client.get(url)
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
        data = response.json()
        assert "error" in data

    @pytest.mark.django_db
    def test_requires_images(self, client, user):
        """Test that request without images returns error."""
        client.force_login(user)
        url = reverse("wine-extract-vision")
        response = client.post(url)
        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "error" in data
        assert "No images" in data["error"]

    @pytest.mark.django_db
    def test_barcode_match_returns_wine_data(self, client, user, wine_factory):
        """Test that matching barcode returns the wine data."""
        # Create a wine with barcode
        wine = wine_factory(
            user=user,
            name="Barcode Match Wine",
            barcode="1234567890123",
            wine_type="RE",
            vintage=2020,
        )

        client.force_login(user)
        url = reverse("wine-extract-vision")

        # Create a test image
        image_file = create_test_image_file()

        # Mock the barcode scanner to return our test barcode
        with patch(
            "wine_cellar.apps.wine.views.BarcodeScanner"
        ) as MockScanner:
            mock_scanner = MagicMock()
            mock_scanner.scan_and_match.return_value = {
                "matched": True,
                "barcode": "1234567890123",
                "wine_data": {
                    "name": "Barcode Match Wine",
                    "wine_type": "RE",
                    "barcode": "1234567890123",
                    "vintage": 2020,
                },
                "all_barcodes": ["1234567890123"],
            }
            MockScanner.return_value = mock_scanner

            response = client.post(
                url,
                {"image_front_label": image_file},
                format="multipart",
            )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["success"] is True
        assert data["match_type"] == "barcode"
        assert data["matched_barcode"] == "1234567890123"
        assert data["data"]["name"] == "Barcode Match Wine"
        assert data["confidence"] == "high"

    @pytest.mark.django_db
    def test_no_barcode_falls_back_to_vision(self, client, user):
        """Test that missing barcode falls back to AI vision extraction."""
        client.force_login(user)
        url = reverse("wine-extract-vision")

        # Create a test image
        image_file = create_test_image_file()

        # Mock both barcode scanner (no match) and vision extractor
        with patch(
            "wine_cellar.apps.wine.views.BarcodeScanner"
        ) as MockScanner, patch(
            "wine_cellar.apps.wine.views.WineVisionExtractor"
        ) as MockVision:
            # Barcode scanner returns no match
            mock_scanner = MagicMock()
            mock_scanner.scan_and_match.return_value = {
                "matched": False,
                "barcode": None,
                "wine_data": None,
                "all_barcodes": [],
            }
            MockScanner.return_value = mock_scanner

            # Vision extractor returns data
            mock_vision = MagicMock()
            mock_vision.extract_from_images.return_value = {
                "data": {
                    "name": "Vision Extracted Wine",
                    "wine_type": "WH",
                    "vintage": 2021,
                },
                "confidence": "medium",
                "extracted_fields": ["name", "wine_type", "vintage"],
                "errors": [],
            }
            MockVision.return_value = mock_vision

            response = client.post(
                url,
                {"image_front_label": image_file},
                format="multipart",
            )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["success"] is True
        assert data["match_type"] == "vision"
        assert data["data"]["name"] == "Vision Extracted Wine"
        assert data["confidence"] == "medium"

    @pytest.mark.django_db
    def test_barcode_found_no_match_adds_to_data(self, client, user):
        """Test that detected barcode is added to data even without match."""
        client.force_login(user)
        url = reverse("wine-extract-vision")

        # Create a test image
        image_file = create_test_image_file()

        # Mock barcode scanner (barcode found but no match) and vision extractor
        with patch(
            "wine_cellar.apps.wine.views.BarcodeScanner"
        ) as MockScanner, patch(
            "wine_cellar.apps.wine.views.WineVisionExtractor"
        ) as MockVision:
            # Barcode scanner finds barcode but no match
            mock_scanner = MagicMock()
            mock_scanner.scan_and_match.return_value = {
                "matched": False,
                "barcode": None,
                "wine_data": None,
                "all_barcodes": ["9876543210987"],
            }
            MockScanner.return_value = mock_scanner

            # Vision extractor returns data without barcode
            mock_vision = MagicMock()
            mock_vision.extract_from_images.return_value = {
                "data": {
                    "name": "Vision Wine",
                },
                "confidence": "low",
                "extracted_fields": ["name"],
                "errors": [],
            }
            MockVision.return_value = mock_vision

            response = client.post(
                url,
                {"image_front_label": image_file},
                format="multipart",
            )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["success"] is True
        # Barcode should be added to data
        assert data["data"]["barcode"] == "9876543210987"
        assert "barcode" in data["extracted_fields"]

    @pytest.mark.django_db
    def test_multiple_images_processed(self, client, user):
        """Test that multiple uploaded images are processed."""
        client.force_login(user)
        url = reverse("wine-extract-vision")

        # Create test images
        image_front = create_test_image_file()
        image_back = create_test_image_file()

        with patch(
            "wine_cellar.apps.wine.views.BarcodeScanner"
        ) as MockScanner, patch(
            "wine_cellar.apps.wine.views.WineVisionExtractor"
        ) as MockVision:
            mock_scanner = MagicMock()
            mock_scanner.scan_and_match.return_value = {
                "matched": False,
                "barcode": None,
                "wine_data": None,
                "all_barcodes": [],
            }
            MockScanner.return_value = mock_scanner

            mock_vision = MagicMock()
            mock_vision.extract_from_images.return_value = {
                "data": {"name": "Multi Image Wine"},
                "confidence": "high",
                "extracted_fields": ["name"],
                "errors": [],
            }
            MockVision.return_value = mock_vision

            response = client.post(
                url,
                {
                    "image_front_label": image_front,
                    "image_back_label": image_back,
                },
                format="multipart",
            )

        assert response.status_code == HTTPStatus.OK
        # Verify both scanner and vision received images
        mock_scanner.scan_and_match.assert_called_once()
        call_args = mock_scanner.scan_and_match.call_args[0]
        assert len(call_args[0]) == 2  # Two images

    @pytest.mark.django_db
    def test_vision_errors_included_in_response(self, client, user):
        """Test that vision extraction errors are included in response."""
        client.force_login(user)
        url = reverse("wine-extract-vision")

        image_file = create_test_image_file()

        with patch(
            "wine_cellar.apps.wine.views.BarcodeScanner"
        ) as MockScanner, patch(
            "wine_cellar.apps.wine.views.WineVisionExtractor"
        ) as MockVision:
            mock_scanner = MagicMock()
            mock_scanner.scan_and_match.return_value = {
                "matched": False,
                "barcode": None,
                "wine_data": None,
                "all_barcodes": [],
            }
            MockScanner.return_value = mock_scanner

            mock_vision = MagicMock()
            mock_vision.extract_from_images.return_value = {
                "data": {},
                "confidence": "low",
                "extracted_fields": [],
                "errors": ["Could not read label", "Image too blurry"],
            }
            MockVision.return_value = mock_vision

            response = client.post(
                url,
                {"image_front_label": image_file},
                format="multipart",
            )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["success"] is True
        assert len(data["errors"]) == 2
        assert "Could not read label" in data["errors"]

    @pytest.mark.django_db
    def test_exception_handling(self, client, user):
        """Test that exceptions are handled gracefully."""
        client.force_login(user)
        url = reverse("wine-extract-vision")

        image_file = create_test_image_file()

        with patch(
            "wine_cellar.apps.wine.views.BarcodeScanner"
        ) as MockScanner:
            MockScanner.side_effect = Exception("Test exception")

            response = client.post(
                url,
                {"image_front_label": image_file},
                format="multipart",
            )

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        data = response.json()
        assert "error" in data
