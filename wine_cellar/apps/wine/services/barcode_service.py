"""Barcode scanning and wine matching service."""

import base64
import io
import logging
from typing import Optional

from PIL import Image, ImageEnhance, ImageFilter

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

    def _preprocess_image(self, img: Image.Image) -> list[Image.Image]:
        """
        Generate preprocessed versions of an image for barcode detection.

        Returns:
            List of PIL images to try for barcode detection
        """
        gray = img.convert("L")
        versions = [gray]

        # High contrast
        versions.append(ImageEnhance.Contrast(gray).enhance(2.0))

        # Sharpened
        versions.append(gray.filter(ImageFilter.SHARPEN))

        return versions

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

        barcodes = set()

        for base64_image in base64_images:
            pil_image = None
            try:
                image_data = base64.b64decode(base64_image)
                pil_image = Image.open(io.BytesIO(image_data))

                if pil_image.mode == "RGBA":
                    pil_image = pil_image.convert("RGB")

                # Try original image first
                decoded_barcodes = pyzbar.decode(pil_image)
                for barcode in decoded_barcodes:
                    try:
                        barcode_data = barcode.data.decode("utf-8")
                        logger.info(
                            f"Found barcode: {barcode_data} (type: {barcode.type})"
                        )
                        barcodes.add(barcode_data)
                    except UnicodeDecodeError:
                        continue

                # If no barcodes found, try preprocessed versions
                if not barcodes:
                    for processed_img in self._preprocess_image(pil_image):
                        decoded_barcodes = pyzbar.decode(processed_img)
                        for barcode in decoded_barcodes:
                            try:
                                barcode_data = barcode.data.decode("utf-8")
                                logger.info(
                                    "Found barcode: %s (type: %s)",
                                    barcode_data,
                                    barcode.type,
                                )
                                barcodes.add(barcode_data)
                            except UnicodeDecodeError:
                                continue
                        if barcodes:
                            break

            except Exception as e:
                logger.warning(f"Error scanning image for barcodes: {e}")
                continue
            finally:
                if pil_image is not None:
                    pil_image.close()

        return list(barcodes)

    def _barcode_variants(self, barcode: str) -> set[str]:
        """Return the cleaned barcode and its UPC-A/EAN-13 variants."""
        barcode_clean = barcode.strip()
        variants = {barcode_clean}
        if len(barcode_clean) == 12:
            variants.add(f"0{barcode_clean}")
        elif len(barcode_clean) == 13 and barcode_clean.startswith("0"):
            variants.add(barcode_clean[1:])
        return variants

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
        wines = self.get_wines_by_barcode(barcode, user)
        return wines.first() if wines is not None else None

    def get_wines_by_barcode(self, barcode: str, user):
        """
        Find all wines matching a barcode with robust matching.

        Handles:
        - Whitespace stripping (input and DB)
        - Leading zero variations (UPC-A vs EAN-13)

        Args:
            barcode: Barcode string to search for
            user: The user to search wines for

        Returns:
            Wine queryset of matching wines, or None on error/empty barcode
        """
        from django.db.models import Count, Q

        from wine_cellar.apps.wine.models import Wine, WineBarcode

        if not barcode:
            return None

        variants = self._barcode_variants(barcode)

        try:
            # 1. Try exact matches on variants
            query = Q()
            for variant in variants:
                query |= Q(barcode=variant)

            wine_pks = list(
                WineBarcode.objects.filter(query, user=user)
                .select_related("wine")
                .values_list("wine_id", flat=True)
                .distinct()
            )

            # 2. If no exact hits, try lax whitespace match
            if not wine_pks:
                search_term = max(variants, key=len)
                for wb in WineBarcode.objects.filter(
                    user=user, barcode__icontains=search_term
                ).select_related("wine"):
                    if wb.barcode and wb.barcode.strip() in variants:
                        wine_pks.append(wb.wine_id)

            if wine_pks:
                return (
                    Wine.objects.filter(pk__in=wine_pks, deleted=False)
                    .select_related("size")
                    .prefetch_related("wineimage_set")
                    .annotate(
                        stock_count=Count(
                            "storageitem",
                            filter=Q(storageitem__deleted=False),
                            distinct=True,
                        )
                    )
                )

        except Exception as e:
            logger.error(f"Error finding wines by barcode: {e}")

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
                - multiple_matches: True if more than one wine matched
                - barcode: The barcode that matched (if any)
                - wine_data: The matched wine data (if any, single match)
                - wines: List of wine summary dicts (if multiple matches)
                - all_barcodes: All barcodes found in images
        """
        result = {
            "matched": False,
            "multiple_matches": False,
            "barcode": None,
            "wine_data": None,
            "wines": [],
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
            wines_qs = self.get_wines_by_barcode(barcode, user)
            if wines_qs is not None and wines_qs.exists():
                result["matched"] = True
                result["barcode"] = barcode

                if wines_qs.count() > 1:
                    result["multiple_matches"] = True
                    result["wines"] = [self._wine_to_summary(w) for w in wines_qs]
                else:
                    result["wine_data"] = self._wine_to_dict(wines_qs.first())
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
        barcodes = list(wine.barcodes.values_list("barcode", flat=True))
        data = {
            "name": wine.name,
            "wine_type": wine.wine_type,
            "barcode": barcodes[0] if barcodes else None,
            "barcodes": barcodes,
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

    def _wine_to_summary(self, wine) -> dict:
        """
        Convert a Wine model instance to a lightweight summary for selection UI.

        Args:
            wine: Wine model instance (should have stock_count annotation)

        Returns:
            dict with pk, name, vintage, wine_type, country, stock_count, thumbnail
        """
        return {
            "pk": wine.pk,
            "name": wine.name,
            "vintage": wine.vintage,
            "wine_type": wine.get_type if wine.wine_type else None,
            "country": wine.country_name if wine.country else None,
            "stock_count": getattr(wine, "stock_count", 0),
            "thumbnail": wine.image_thumbnail,
        }
