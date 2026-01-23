"""Barcode scanning and wine matching service."""

import base64
import io
import logging
from typing import Optional

import cv2
import numpy as np
from PIL import Image

try:
    from pyzbar import pyzbar
except ImportError:
    pyzbar = None

logger = logging.getLogger(__name__)


class BarcodeScanner:
    """Service for scanning barcodes from images and matching against existing wines."""

    def __init__(self):
        """Initialize the scanner."""
        self._pyzbar_available = None

    def _check_pyzbar(self) -> bool:
        """Check if pyzbar is available."""
        if self._pyzbar_available is None:
            if pyzbar is not None:
                self._pyzbar_available = True
            else:
                logger.warning("pyzbar not available. Install with: pip install pyzbar")
                self._pyzbar_available = False
        return self._pyzbar_available

    def _preprocess_image(self, img: np.ndarray) -> list[np.ndarray]:
        """
        Generate multiple preprocessed versions of an image for barcode detection.

        Args:
            img: OpenCV image (BGR or grayscale)

        Returns:
            List of preprocessed images to try for barcode detection
        """
        versions = []

        # Convert to grayscale if needed
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # 1. Simple grayscale
        versions.append(gray)

        # 2. CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        clahe_img = clahe.apply(gray)
        versions.append(clahe_img)

        # 3. Adaptive thresholding
        adaptive = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        versions.append(adaptive)

        # 4. Otsu's binary thresholding
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        versions.append(otsu)

        # 5. Sharpened image
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        sharpened = cv2.filter2D(gray, -1, kernel)
        versions.append(sharpened)

        return versions

    def scan_images_for_barcodes(self, base64_images: list[str]) -> list[str]:
        """
        Scan multiple images for barcodes using various preprocessing techniques.

        Args:
            base64_images: List of base64-encoded image data

        Returns:
            List of detected barcode strings (deduplicated)
        """
        if not self._check_pyzbar():
            return []

        barcodes = set()

        for base64_image in base64_images:
            pil_image = None
            try:
                # Decode base64 to image
                image_data = base64.b64decode(base64_image)
                pil_image = Image.open(io.BytesIO(image_data))

                # Convert PIL Image to OpenCV format
                if pil_image.mode == "RGBA":
                    pil_image = pil_image.convert("RGB")
                cv_image = np.array(pil_image)
                if len(cv_image.shape) == 3:
                    cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)

                # Try original image first (color can help with some barcodes)
                decoded_barcodes = pyzbar.decode(cv_image)
                for barcode in decoded_barcodes:
                    try:
                        barcode_data = barcode.data.decode("utf-8")
                        barcode_type = barcode.type
                        logger.info(
                            f"Found barcode: {barcode_data} (type: {barcode_type})"
                        )
                        barcodes.add(barcode_data)
                    except UnicodeDecodeError:
                        logger.warning(
                            f"Skipping barcode with non-UTF-8 data: {barcode.data}"
                        )
                        continue

                # If no barcodes found, try preprocessed versions
                if not barcodes:
                    preprocessed_versions = self._preprocess_image(cv_image)
                    for i, processed_img in enumerate(preprocessed_versions):
                        decoded_barcodes = pyzbar.decode(processed_img)
                        for barcode in decoded_barcodes:
                            try:
                                barcode_data = barcode.data.decode("utf-8")
                                barcode_type = barcode.type
                                logger.info(
                                    f"Found barcode with preprocessing #{i}: "
                                    f"{barcode_data} (type: {barcode_type})"
                                )
                                barcodes.add(barcode_data)
                            except UnicodeDecodeError:
                                logger.warning(
                                    f"Skipping barcode with non-UTF-8 data: "
                                    f"{barcode.data}"
                                )
                                continue
                        # Stop if we found barcodes
                        if barcodes:
                            break

            except Exception as e:
                logger.warning(f"Error scanning image for barcodes: {e}")
                continue
            finally:
                # Explicitly close PIL Image objects to free resources
                if pil_image is not None:
                    pil_image.close()

        return list(barcodes)

    def get_wine_object_by_barcode(self, barcode: str, user):
        """
        Find a wine object in the database by barcode with robust matching.

        Handles:
        - Whitespace stripping (input and DB)
        - Leading zero variations (UPC-A vs EAN-13)

        Args:
            barcode: Barcode string to search for
            user: The user to search wines for

        Returns:
            Wine model instance if found, None otherwise
        """
        from django.db.models import Q

        from wine_cellar.apps.wine.models import Wine

        if not barcode:
            return None

        barcode_clean = barcode.strip()

        # Potential variants to check
        variants = {barcode_clean}
        if len(barcode_clean) == 12:
            variants.add(f"0{barcode_clean}")
        elif len(barcode_clean) == 13 and barcode_clean.startswith("0"):
            variants.add(barcode_clean[1:])

        try:
            # 1. Try exact matches on variants
            query = Q()
            for variant in variants:
                query |= Q(barcode=variant)

            # Try finding exact matches first
            wine = Wine.objects.filter(query, user=user).first()
            if wine:
                return wine

            # 2. If failure, try lax whitespace match
            # (This handles the case where DB has " 123 ")
            # We use the longest variant for safety to avoid matching partials too
            # aggressively
            search_term = max(variants, key=len)
            wines = Wine.objects.filter(user=user, barcode__icontains=search_term)
            for wine in wines:
                if wine.barcode and wine.barcode.strip() in variants:
                    return wine

        except Exception as e:
            logger.error(f"Error finding wine object by barcode: {e}")

        return None

    def find_wine_by_barcode(self, barcode: str, user) -> Optional[dict]:
        """
        Find a wine in the database by barcode.

        Args:
            barcode: Barcode string to search for
            user: The user to search wines for

        Returns:
            Wine data dict if found, None otherwise
        """
        wine = self.get_wine_object_by_barcode(barcode, user)

        if wine:
            logger.info(f"Found existing wine with barcode {barcode}: {wine.name}")
            return self._wine_to_dict(wine)

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
