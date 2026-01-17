"""Barcode scanning and wine matching service."""

import base64
import io
import logging
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)


class BarcodeScanner:
    """Service for scanning barcodes from images and matching against existing wines."""

    def __init__(self):
        """Initialize the scanner."""
        self._pyzbar_available = None

    def _check_pyzbar(self) -> bool:
        """Check if pyzbar is available."""
        if self._pyzbar_available is None:
            try:
                from pyzbar import pyzbar  # noqa: F401

                self._pyzbar_available = True
            except ImportError:
                logger.warning("pyzbar not available. Install with: pip install pyzbar")
                self._pyzbar_available = False
            except Exception as e:
                logger.warning(
                    f"pyzbar import error (libzbar may not be installed): {e}"
                )
                self._pyzbar_available = False
        return self._pyzbar_available

    def scan_images_for_barcodes(self, base64_images: list[str]) -> list[str]:
        """
        Scan multiple images for barcodes.

        Args:
            base64_images: List of base64-encoded image data

        Returns:
            List of detected barcode strings (deduplicated)
        """
        if not self._check_pyzbar():
            return []

        from pyzbar import pyzbar

        barcodes = set()

        for base64_image in base64_images:
            image = None
            gray_image = None
            try:
                # Decode base64 to image
                image_data = base64.b64decode(base64_image)
                image = Image.open(io.BytesIO(image_data))

                # Convert to grayscale for better detection
                if image.mode != "L":
                    gray_image = image.convert("L")
                else:
                    gray_image = image

                # Decode barcodes
                decoded_barcodes = pyzbar.decode(gray_image)

                for barcode in decoded_barcodes:
                    try:
                        barcode_data = barcode.data.decode("utf-8")
                        barcode_type = barcode.type
                        logger.info(
                            f"Found barcode: {barcode_data} (type: {barcode_type})"
                        )
                        barcodes.add(barcode_data)
                    except UnicodeDecodeError:
                        # Skip barcodes with non-UTF-8 data
                        logger.warning(
                            f"Skipping barcode with non-UTF-8 data: {barcode.data}"
                        )
                        continue

                # Also try original image (sometimes color helps with certain barcodes)
                if image.mode != "L":
                    decoded_barcodes = pyzbar.decode(image)
                    for barcode in decoded_barcodes:
                        try:
                            barcode_data = barcode.data.decode("utf-8")
                            barcodes.add(barcode_data)
                        except UnicodeDecodeError:
                            # Skip barcodes with non-UTF-8 data
                            logger.warning(
                                f"Skipping barcode with non-UTF-8 data: {barcode.data}"
                            )
                            continue

            except Exception as e:
                logger.warning(f"Error scanning image for barcodes: {e}")
                continue
            finally:
                # Explicitly close PIL Image objects to free resources
                if gray_image is not None and gray_image is not image:
                    gray_image.close()
                if image is not None:
                    image.close()

        return list(barcodes)

    def find_wine_by_barcode(self, barcode: str, user) -> Optional[dict]:
        """
        Find a wine in the database by barcode.

        Args:
            barcode: Barcode string to search for
            user: The user to search wines for

        Returns:
            Wine data dict if found, None otherwise
        """
        from wine_cellar.apps.wine.models import Wine

        try:
            wine = Wine.objects.filter(user=user, barcode=barcode).first()

            if wine:
                logger.info(f"Found existing wine with barcode {barcode}: {wine.name}")
                return self._wine_to_dict(wine)

        except Exception as e:
            logger.error(f"Error finding wine by barcode: {e}")

        return None

    def scan_and_match(self, base64_images: list[str], user) -> dict:
        """
        Scan images for barcodes and try to match against existing wines.

        Args:
            base64_images: List of base64-encoded image data
            user: The user to search wines for

        Returns:
            dict with keys:
                - matched: True if a wine was found
                - barcode: The barcode that matched (if any)
                - wine_data: The matched wine data (if any)
                - all_barcodes: All barcodes found in images
        """
        result = {
            "matched": False,
            "barcode": None,
            "wine_data": None,
            "all_barcodes": [],
        }

        # Scan all images for barcodes
        barcodes = self.scan_images_for_barcodes(base64_images)
        result["all_barcodes"] = barcodes

        if not barcodes:
            logger.info("No barcodes found in images")
            return result

        # Try to match each barcode against existing wines
        for barcode in barcodes:
            wine_data = self.find_wine_by_barcode(barcode, user)
            if wine_data:
                result["matched"] = True
                result["barcode"] = barcode
                result["wine_data"] = wine_data
                return result

        logger.info(f"Barcodes found but no matching wines: {barcodes}")
        return result

    def _wine_to_dict(self, wine) -> dict:
        """
        Convert a Wine model instance to a dictionary for form filling.

        Args:
            wine: Wine model instance

        Returns:
            dict with wine data matching form fields
        """
        data = {
            "name": wine.name,
            "wine_type": wine.wine_type,
            "barcode": wine.barcode,
        }

        # Add optional fields if present
        if wine.vintage:
            data["vintage"] = wine.vintage
        if wine.country:
            data["country"] = wine.country
        if wine.subregion:
            data["subregion"] = wine.subregion
        if wine.abv:
            data["abv"] = float(wine.abv)
        if wine.size:
            data["size"] = wine.size.name
        if wine.category:
            data["category"] = wine.category
        if wine.price:
            data["price"] = str(wine.price)
        if wine.rrp:
            data["rrp"] = str(wine.rrp)

        # Handle many-to-many fields
        grapes = list(wine.grapes.values_list("name", flat=True))
        if grapes:
            data["grapes"] = grapes

        attributes = list(wine.attributes.values_list("name", flat=True))
        if attributes:
            data["attributes"] = attributes

        vineyards = list(wine.vineyard.values_list("name", flat=True))
        if vineyards:
            data["vineyard"] = vineyards

        return data
