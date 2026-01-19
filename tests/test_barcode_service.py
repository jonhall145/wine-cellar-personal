"""Tests for barcode scanning service."""

import base64
import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from wine_cellar.apps.wine.services.barcode_service import BarcodeScanner


def create_unicode_error_barcode_mock():
    """Helper to create a barcode mock that raises UnicodeDecodeError."""
    mock_barcode = MagicMock()
    mock_barcode.data = MagicMock()
    mock_barcode.data.decode.side_effect = UnicodeDecodeError(
        "utf-8", b"\xff\xfe", 0, 2, "invalid start byte"
    )
    return mock_barcode


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

    @patch(
        "wine_cellar.apps.wine.services.barcode_service.BarcodeScanner._check_pyzbar"
    )
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

        with patch(
            "wine_cellar.apps.wine.services.barcode_service.pyzbar"
        ) as mock_pyzbar:
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
    def test_find_wine_by_barcode_other_user(self, user, user_factory, wine_factory):
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

    @patch(
        "wine_cellar.apps.wine.services.barcode_service.BarcodeScanner._check_pyzbar"
    )
    def test_unicode_decode_error_handling_grayscale(self, mock_check):
        """Test that non-UTF-8 barcode data is handled gracefully in grayscale scan."""
        mock_check.return_value = True
        scanner = BarcodeScanner()
        scanner._pyzbar_available = True

        # Create a dummy base64 image
        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

        with patch(
            "wine_cellar.apps.wine.services.barcode_service.pyzbar"
        ) as mock_pyzbar:
            # Mock barcode with non-UTF-8 data
            mock_barcode = create_unicode_error_barcode_mock()
            mock_pyzbar.decode.return_value = [mock_barcode]

            # Should not raise exception, should skip the barcode
            result = scanner.scan_images_for_barcodes([base64_image])

            # Result should be empty since the barcode was skipped
            assert result == []

    @patch(
        "wine_cellar.apps.wine.services.barcode_service.BarcodeScanner._check_pyzbar"
    )
    def test_unicode_decode_error_handling_color(self, mock_check):
        """Test that non-UTF-8 barcode data is handled gracefully in color scan."""
        mock_check.return_value = True
        scanner = BarcodeScanner()
        scanner._pyzbar_available = True

        # Create a dummy base64 image (color mode, not grayscale)
        img = Image.new("RGB", (100, 100), color="blue")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

        with patch(
            "wine_cellar.apps.wine.services.barcode_service.pyzbar"
        ) as mock_pyzbar:
            # Mock barcode with non-UTF-8 data for both grayscale and color scans
            mock_barcode = create_unicode_error_barcode_mock()

            # Return the bad barcode for both grayscale and color scans
            mock_pyzbar.decode.return_value = [mock_barcode]

            # Should not raise exception, should skip the barcode
            result = scanner.scan_images_for_barcodes([base64_image])

            # Result should be empty since the barcode was skipped
            assert result == []

    @patch(
        "wine_cellar.apps.wine.services.barcode_service.BarcodeScanner._check_pyzbar"
    )
    def test_mixed_valid_and_invalid_barcodes(self, mock_check):
        """Test that valid barcodes are still returned when some have UTF-8 errors."""
        mock_check.return_value = True
        scanner = BarcodeScanner()
        scanner._pyzbar_available = True

        # Create a dummy base64 image
        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

        with patch(
            "wine_cellar.apps.wine.services.barcode_service.pyzbar"
        ) as mock_pyzbar:
            # Mock one valid and one invalid barcode
            valid_barcode = MagicMock()
            valid_barcode.data.decode.return_value = "1234567890123"
            valid_barcode.type = "EAN13"

            invalid_barcode = create_unicode_error_barcode_mock()

            mock_pyzbar.decode.return_value = [valid_barcode, invalid_barcode]

            result = scanner.scan_images_for_barcodes([base64_image])

            # Should only include the valid barcode
            assert "1234567890123" in result
            assert len(result) == 1

    @patch(
        "wine_cellar.apps.wine.services.barcode_service.BarcodeScanner._check_pyzbar"
    )
    def test_pil_image_cleanup_on_success(self, mock_check):
        """Test that PIL Image objects are closed after successful processing."""
        mock_check.return_value = True
        scanner = BarcodeScanner()
        scanner._pyzbar_available = True

        # Create a dummy base64 image
        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

        with (
            patch(
                "wine_cellar.apps.wine.services.barcode_service.pyzbar"
            ) as mock_pyzbar,
            patch(
                "wine_cellar.apps.wine.services.barcode_service.Image"
            ) as mock_image_class,
        ):

            # Mock the Image.open to return a mock image
            mock_image = MagicMock()
            mock_gray_image = MagicMock()
            mock_image.mode = "RGB"
            mock_image.convert.return_value = mock_gray_image
            mock_image_class.open.return_value = mock_image

            # Mock barcode detection
            mock_barcode = MagicMock()
            mock_barcode.data.decode.return_value = "1234567890123"
            mock_barcode.type = "EAN13"
            mock_pyzbar.decode.return_value = [mock_barcode]

            result = scanner.scan_images_for_barcodes([base64_image])

            # Verify that close was called on both images
            mock_gray_image.close.assert_called_once()
            mock_image.close.assert_called_once()
            assert "1234567890123" in result

    @patch(
        "wine_cellar.apps.wine.services.barcode_service.BarcodeScanner._check_pyzbar"
    )
    def test_pil_image_cleanup_on_error(self, mock_check):
        """Test that PIL Image objects are closed even when an error occurs."""
        mock_check.return_value = True
        scanner = BarcodeScanner()
        scanner._pyzbar_available = True

        # Create a dummy base64 image
        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

        with (
            patch(
                "wine_cellar.apps.wine.services.barcode_service.pyzbar"
            ) as mock_pyzbar,
            patch(
                "wine_cellar.apps.wine.services.barcode_service.Image"
            ) as mock_image_class,
        ):

            # Mock the Image.open to return a mock image
            mock_image = MagicMock()
            mock_gray_image = MagicMock()
            mock_image.mode = "RGB"
            mock_image.convert.return_value = mock_gray_image
            mock_image_class.open.return_value = mock_image

            # Make pyzbar.decode raise an exception
            mock_pyzbar.decode.side_effect = Exception("Test error")

            # Should not raise exception due to try/except
            result = scanner.scan_images_for_barcodes([base64_image])

            # Verify that close was still called on both images despite the error
            mock_gray_image.close.assert_called_once()
            mock_image.close.assert_called_once()
            assert result == []

    @patch(
        "wine_cellar.apps.wine.services.barcode_service.BarcodeScanner._check_pyzbar"
    )
    def test_pil_image_cleanup_grayscale_mode(self, mock_check):
        """Test that only one close is called when image is already grayscale."""
        mock_check.return_value = True
        scanner = BarcodeScanner()
        scanner._pyzbar_available = True

        # Create a grayscale base64 image
        img = Image.new("L", (100, 100), color=128)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

        with (
            patch(
                "wine_cellar.apps.wine.services.barcode_service.pyzbar"
            ) as mock_pyzbar,
            patch(
                "wine_cellar.apps.wine.services.barcode_service.Image"
            ) as mock_image_class,
        ):

            # Mock the Image.open to return a grayscale mock image
            mock_image = MagicMock()
            mock_image.mode = "L"  # Already grayscale
            mock_image_class.open.return_value = mock_image

            # Mock barcode detection
            mock_barcode = MagicMock()
            mock_barcode.data.decode.return_value = "1234567890123"
            mock_barcode.type = "EAN13"
            mock_pyzbar.decode.return_value = [mock_barcode]

            result = scanner.scan_images_for_barcodes([base64_image])

            # Verify that close was called only once (no separate gray_image)
            mock_image.close.assert_called_once()
            assert "1234567890123" in result
