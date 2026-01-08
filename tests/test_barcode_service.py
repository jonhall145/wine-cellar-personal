"""Tests for barcode scanning service."""

import base64
import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from wine_cellar.apps.wine.services.barcode_service import BarcodeScanner


class TestBarcodeScanner:
    """Tests for the BarcodeScanner class."""

    def test_check_pyzbar_available(self):
        """Test pyzbar availability check."""
        scanner = BarcodeScanner()
        # Just verify it doesn't crash - actual availability depends on system
        result = scanner._check_pyzbar()
        assert isinstance(result, bool)

    def test_scan_images_for_barcodes_empty_list(self):
        """Test scanning empty image list returns empty list."""
        scanner = BarcodeScanner()
        result = scanner.scan_images_for_barcodes([])
        assert result == []

    def test_scan_images_for_barcodes_no_pyzbar(self):
        """Test scanning returns empty when pyzbar unavailable."""
        scanner = BarcodeScanner()
        scanner._pyzbar_available = False

        # Create a dummy base64 image
        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

        result = scanner.scan_images_for_barcodes([base64_image])
        assert result == []

    @patch("wine_cellar.apps.wine.services.barcode_service.BarcodeScanner._check_pyzbar")
    def test_scan_images_for_barcodes_with_mock(self, mock_check):
        """Test barcode scanning with mocked pyzbar."""
        mock_check.return_value = True
        scanner = BarcodeScanner()
        scanner._pyzbar_available = True

        # Create a dummy base64 image
        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

        with patch("wine_cellar.apps.wine.services.barcode_service.pyzbar") as mock_pyzbar:
            # Mock barcode detection
            mock_barcode = MagicMock()
            mock_barcode.data.decode.return_value = "1234567890123"
            mock_barcode.type = "EAN13"
            mock_pyzbar.decode.return_value = [mock_barcode]

            result = scanner.scan_images_for_barcodes([base64_image])

            assert "1234567890123" in result

    def test_scan_images_handles_invalid_base64(self):
        """Test that invalid base64 data is handled gracefully."""
        scanner = BarcodeScanner()
        scanner._pyzbar_available = True

        # This should not raise an exception
        result = scanner.scan_images_for_barcodes(["not-valid-base64!!!"])
        assert result == []

    @pytest.mark.django_db
    def test_find_wine_by_barcode_no_match(self, user):
        """Test finding wine when no match exists."""
        scanner = BarcodeScanner()
        result = scanner.find_wine_by_barcode("9999999999", user)
        assert result is None

    @pytest.mark.django_db
    def test_find_wine_by_barcode_with_match(self, user, wine_factory):
        """Test finding wine when match exists."""
        wine_factory(user=user, barcode="1234567890123", name="Test Wine")

        scanner = BarcodeScanner()
        result = scanner.find_wine_by_barcode("1234567890123", user)

        assert result is not None
        assert result["name"] == "Test Wine"
        assert result["barcode"] == "1234567890123"

    @pytest.mark.django_db
    def test_find_wine_by_barcode_different_user(self, user, user_factory, wine_factory):
        """Test that barcode lookup only finds wines for the correct user."""
        other_user = user_factory()
        wine_factory(user=other_user, barcode="1234567890123", name="Other User Wine")

        scanner = BarcodeScanner()
        result = scanner.find_wine_by_barcode("1234567890123", user)

        assert result is None

    @pytest.mark.django_db
    def test_scan_and_match_no_images(self, user):
        """Test scan_and_match with no images."""
        scanner = BarcodeScanner()
        result = scanner.scan_and_match([], user)

        assert result["matched"] is False
        assert result["barcode"] is None
        assert result["wine_data"] is None
        assert result["all_barcodes"] == []

    @pytest.mark.django_db
    def test_scan_and_match_no_barcodes_found(self, user):
        """Test scan_and_match when no barcodes are detected."""
        scanner = BarcodeScanner()
        scanner._pyzbar_available = False  # Disable pyzbar to simulate no detection

        # Create a dummy base64 image
        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

        result = scanner.scan_and_match([base64_image], user)

        assert result["matched"] is False
        assert result["all_barcodes"] == []

    @pytest.mark.django_db
    def test_scan_and_match_barcode_found_with_match(self, user, wine_factory):
        """Test scan_and_match when barcode is found and matches a wine."""
        wine_factory(user=user, barcode="1234567890123", name="Matched Wine")

        scanner = BarcodeScanner()
        # Mock the barcode scanning to return our test barcode
        with patch.object(scanner, "scan_images_for_barcodes") as mock_scan:
            mock_scan.return_value = ["1234567890123"]

            result = scanner.scan_and_match(["dummy_image"], user)

        assert result["matched"] is True
        assert result["barcode"] == "1234567890123"
        assert result["wine_data"]["name"] == "Matched Wine"

    @pytest.mark.django_db
    def test_scan_and_match_barcode_found_no_match(self, user):
        """Test scan_and_match when barcode is found but doesn't match any wine."""
        scanner = BarcodeScanner()
        # Mock the barcode scanning to return a barcode
        with patch.object(scanner, "scan_images_for_barcodes") as mock_scan:
            mock_scan.return_value = ["9999999999999"]

            result = scanner.scan_and_match(["dummy_image"], user)

        assert result["matched"] is False
        assert result["barcode"] is None
        assert result["all_barcodes"] == ["9999999999999"]

    @pytest.mark.django_db
    def test_wine_to_dict_basic_fields(self, user, wine_factory):
        """Test _wine_to_dict includes basic fields."""
        wine = wine_factory(
            user=user,
            name="Test Wine",
            wine_type="RE",
            barcode="123456",
            vintage=2020,
            country="FR",
            abv=13.5,
        )

        scanner = BarcodeScanner()
        result = scanner._wine_to_dict(wine)

        assert result["name"] == "Test Wine"
        assert result["wine_type"] == "RE"
        assert result["barcode"] == "123456"
        assert result["vintage"] == 2020
        assert result["country"] == "FR"
        assert result["abv"] == 13.5

    @pytest.mark.django_db
    def test_wine_to_dict_with_grapes(self, user, wine_factory, grape_factory):
        """Test _wine_to_dict includes grape names."""
        grape1 = grape_factory(name="Merlot")
        grape2 = grape_factory(name="Cabernet")
        wine = wine_factory(user=user, grapes=[grape1, grape2])

        scanner = BarcodeScanner()
        result = scanner._wine_to_dict(wine)

        assert "grapes" in result
        assert set(result["grapes"]) == {"Merlot", "Cabernet"}

    @pytest.mark.django_db
    def test_wine_to_dict_with_attributes(self, user, wine_factory, attribute_factory):
        """Test _wine_to_dict includes attribute names."""
        attr1 = attribute_factory(name="Organic")
        attr2 = attribute_factory(name="Vegan")
        wine = wine_factory(user=user)
        wine.attributes.add(attr1, attr2)

        scanner = BarcodeScanner()
        result = scanner._wine_to_dict(wine)

        assert "attributes" in result
        assert set(result["attributes"]) == {"Organic", "Vegan"}
