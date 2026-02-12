"""Barcode scanning and whisky matching service."""

import logging

from wine_cellar.apps.wine.services.barcode_service import BarcodeScanner

logger = logging.getLogger(__name__)


class WhiskyBarcodeScanner(BarcodeScanner):
    """Scan barcodes from images and match against existing whiskies."""

    def get_whisky_by_barcode(self, barcode: str, user):
        """
        Find a whisky in the database by barcode.

        Args:
            barcode: Barcode string to search for
            user: The user to search whiskies for

        Returns:
            Whisky data dict if found, None otherwise
        """
        whisky = self._get_whisky_object_by_barcode(barcode, user)
        if whisky:
            logger.info(f"Found existing whisky with barcode {barcode}: {whisky.name}")
            return self._whisky_to_dict(whisky)
        return None

    def _get_whisky_object_by_barcode(self, barcode: str, user):
        """Find a whisky object by barcode with robust matching."""
        whiskies = self._get_whiskies_by_barcode(barcode, user)
        return whiskies.first() if whiskies is not None else None

    def _get_whiskies_by_barcode(self, barcode: str, user):
        """Find all whiskies matching a barcode."""
        from django.db.models import Count, Q

        from wine_cellar.apps.whisky.models import Whisky, WhiskyBarcode

        if not barcode:
            return None

        variants = self._barcode_variants(barcode)

        try:
            query = Q()
            for variant in variants:
                query |= Q(barcode=variant)

            whisky_pks = list(
                WhiskyBarcode.objects.filter(query, user=user)
                .select_related("whisky")
                .values_list("whisky_id", flat=True)
                .distinct()
            )

            if not whisky_pks:
                search_term = max(variants, key=len)
                for wb in WhiskyBarcode.objects.filter(
                    user=user, barcode__icontains=search_term
                ).select_related("whisky"):
                    if wb.barcode and wb.barcode.strip() in variants:
                        whisky_pks.append(wb.whisky_id)

            if whisky_pks:
                return (
                    Whisky.objects.filter(pk__in=whisky_pks)
                    .select_related("distillery", "region", "bottler")
                    .prefetch_related("images")
                    .annotate(
                        stock_count=Count(
                            "whiskystorageitem",
                            filter=Q(whiskystorageitem__deleted=False),
                            distinct=True,
                        )
                    )
                )

        except Exception as e:
            logger.error(f"Error finding whiskies by barcode: {e}")

        return None

    def scan_and_match(self, base64_images: list[str], user) -> dict:
        """
        Scan images for barcodes and try to match against existing whiskies.

        Args:
            base64_images: List of base64-encoded image data
            user: The user to search whiskies for

        Returns:
            dict with match results
        """
        result = {
            "matched": False,
            "multiple_matches": False,
            "barcode": None,
            "whisky_data": None,
            "whiskies": [],
            "all_barcodes": [],
        }

        barcodes = self.scan_images_for_barcodes(base64_images)
        result["all_barcodes"] = barcodes

        if not barcodes:
            logger.info("No barcodes found in images")
            return result

        for barcode in barcodes:
            whiskies_qs = self._get_whiskies_by_barcode(barcode, user)
            if whiskies_qs is not None and whiskies_qs.exists():
                result["matched"] = True
                result["barcode"] = barcode

                if whiskies_qs.count() > 1:
                    result["multiple_matches"] = True
                    result["whiskies"] = [
                        self._whisky_to_summary(w) for w in whiskies_qs
                    ]
                else:
                    result["whisky_data"] = self._whisky_to_dict(whiskies_qs.first())
                return result

        logger.info(f"Barcodes found but no matching whiskies: {barcodes}")
        return result

    def _whisky_to_dict(self, whisky) -> dict:
        """Convert a Whisky model instance to a dictionary for form filling."""
        barcodes = list(whisky.barcodes.values_list("barcode", flat=True))
        data = {
            "name": whisky.name,
            "whisky_type": whisky.whisky_type,
            "barcode": barcodes[0] if barcodes else None,
        }

        if whisky.distillery_id:
            data["distillery"] = whisky.distillery_id
        if whisky.region_id:
            data["region"] = whisky.region_id
        if whisky.country:
            data["country"] = whisky.country
        if whisky.age_statement:
            data["age_statement"] = whisky.age_statement
        if whisky.abv:
            data["abv"] = float(whisky.abv)
        if whisky.size:
            data["size"] = whisky.size
        if whisky.peated_level:
            data["peated_level"] = whisky.peated_level
        if whisky.cask_type:
            data["cask_type"] = whisky.cask_type
        if whisky.vintage_year:
            data["vintage_year"] = whisky.vintage_year
        if whisky.bottled_year:
            data["bottled_year"] = whisky.bottled_year
        if whisky.cask_number:
            data["cask_number"] = whisky.cask_number
        if whisky.batch_number:
            data["batch_number"] = whisky.batch_number
        if whisky.bottle_number:
            data["bottle_number"] = whisky.bottle_number
        if whisky.bottler_id:
            data["bottler"] = whisky.bottler_id
        if whisky.bottler_series:
            data["bottler_series"] = whisky.bottler_series

        return data

    def _whisky_to_summary(self, whisky) -> dict:
        """Convert a Whisky model instance to a lightweight summary."""
        return {
            "pk": whisky.pk,
            "name": whisky.name,
            "age_statement": whisky.age_statement,
            "whisky_type": (
                whisky.get_whisky_type_display() if whisky.whisky_type else None
            ),
            "country": whisky.country_name if whisky.country else None,
            "stock_count": getattr(whisky, "stock_count", 0),
            "thumbnail": whisky.image_thumbnail,
        }
