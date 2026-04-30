import logging

from django.db import transaction
from PIL import Image

from wine_cellar.apps.wine.models import (
    Size,
    Wine,
    WineBarcode,
    WineImage,
    ImageType,
    VisionExtractionLog,
)
from wine_cellar.apps.storage.models import StorageItem
from wine_cellar.apps.wine.utils import apply_manual_crop

logger = logging.getLogger(__name__)


class WineCreationService:
    """Service for wine creation and initialization logic."""

    @staticmethod
    @transaction.atomic
    def create_or_update_wine(user, household, cleaned_data):
        """Create or update a wine with its related objects.
        
        Returns:
            (wine, created) tuple
        """
        abv = cleaned_data["abv"]
        size_code = cleaned_data["size"]
        size = None
        if size_code:
            size, _ = Size.objects.get_or_create(name=size_code, user=None)
        category = cleaned_data["category"] or None
        barcode = cleaned_data["barcode"]
        comment = cleaned_data["comment"]
        country = cleaned_data["country"]
        subregion = cleaned_data["subregion"]
        appellation = cleaned_data.get("appellation")
        food_pairings = cleaned_data["food_pairings"]
        source = cleaned_data["source"]
        price = cleaned_data["price"]
        vineyards = cleaned_data["vineyard"]
        grapes = cleaned_data["grapes"]
        name = cleaned_data["name"]
        rating = cleaned_data["rating"]
        vintage = cleaned_data["vintage"]
        wine_type = cleaned_data["wine_type"]
        attributes = cleaned_data["attributes"]
        drink_from = cleaned_data["drink_from"]
        drink_to = cleaned_data["drink_to"]

        wine, created = Wine.objects.get_or_create(
            name=name,
            wine_type=wine_type,
            abv=abv,
            size=size,
            vintage=vintage,
            country=country,
            user=user,
            household=household,
            deleted=False,
            defaults={
                "category": category,
                "subregion": subregion,
                "appellation": appellation,
                "drink_from": drink_from,
                "drink_to": drink_to,
                "comment": comment,
                "rating": rating,
                "price": price,
            },
        )

        if barcode:
            WineBarcode.objects.get_or_create(
                barcode=barcode,
                user=user,
                defaults={"wine": wine, "household": household},
            )

        wine.vineyard.set(vineyards)
        wine.grapes.set(grapes)
        wine.food_pairings.set(food_pairings)
        wine.source.set(source)
        wine.attributes.set(attributes)

        storage = cleaned_data.get("storage")
        if storage:
            row = cleaned_data.get("row")
            column = cleaned_data.get("column")
            bottle_price = cleaned_data.get("bottle_price") or price
            is_gift = cleaned_data.get("is_gift", False)
            gift_from = cleaned_data.get("gift_from")
            occasion = cleaned_data.get("occasion")
            StorageItem.objects.create(
                storage=storage,
                wine=wine,
                row=row,
                column=column,
                user=user,
                household=household,
                price=bottle_price,
                is_gift=is_gift,
                gift_from=gift_from,
                occasion=occasion,
            )

        return wine, created

    @staticmethod
    def create_wine_images(wine, user, cleaned_data, image_fields_map):
        """Create WineImage records from form data.
        
        Args:
            wine: Wine instance
            user: User instance
            cleaned_data: Form cleaned_data dict
            image_fields_map: Dict mapping field names to ImageType values
        """
        for field_name, image_type in image_fields_map.items():
            image = cleaned_data.get(field_name)
            if not image:
                continue

            WineImage.objects.get_or_create(
                wine=wine,
                image=image,
                user=user,
                image_type=image_type,
            )

    @staticmethod
    def apply_auto_crop_from_extraction(wine, extracted_data):
        """Apply AI-extracted label bounds as auto-crop thumbnails.
        
        Args:
            wine: Wine instance
            extracted_data: Dict of extraction results with label_bounds_front/back
        """
        bounds_map = {
            ImageType.LABEL_FRONT: extracted_data.get("label_bounds_front"),
            ImageType.LABEL_BACK: extracted_data.get("label_bounds_back"),
        }

        for image_type, bounds in bounds_map.items():
            if not bounds:
                continue
            wine_image = wine.wineimage_set.filter(image_type=image_type).first()
            if not wine_image or not wine_image.image:
                continue
            try:
                import os
                from django.conf import settings as django_settings

                full_path = os.path.join(
                    django_settings.MEDIA_ROOT, wine_image.image.name
                )
                with Image.open(full_path) as img:
                    img_width, img_height = img.size

                x = int((bounds["x1"] / 100) * img_width)
                y = int((bounds["y1"] / 100) * img_height)
                width = int(((bounds["x2"] - bounds["x1"]) / 100) * img_width)
                height = int(((bounds["y2"] - bounds["y1"]) / 100) * img_height)

                if width > 0 and height > 0:
                    thumb_path = apply_manual_crop(wine_image, x, y, width, height)
                    wine_image.thumbnail = thumb_path
                    wine_image.save(update_fields=["thumbnail"])
            except Exception:
                logger.exception(
                    f"Auto-crop failed for wine {wine.pk} image type {image_type}"
                )

    @staticmethod
    def link_extraction_log(wine, user, cleaned_data, extraction_result):
        """Link vision extraction log to created wine and record corrections.
        
        Args:
            wine: Wine instance
            user: User instance
            cleaned_data: Form cleaned_data dict
            extraction_result: Dict of extraction results
        """
        try:
            log = (
                VisionExtractionLog.objects.filter(
                    user=user,
                    wine__isnull=True,
                )
                .order_by("-created")
                .first()
            )
            if log:
                corrections = _detect_corrections(cleaned_data, 
                                                 extraction_result.get("extracted_data", {}))
                log.wine = wine
                log.was_successful = True
                if corrections:
                    log.user_corrections = corrections
                log.save(
                    update_fields=[
                        "wine",
                        "was_successful",
                        "user_corrections",
                    ]
                )
        except Exception:
            logger.exception(
                "Failed to link extraction log to wine %s", wine.pk
            )


def _detect_corrections(cleaned_data, extracted_data):
    """Detect differences between extracted data and user-corrected values.
    
    Returns a dict of fields that were different from extraction.
    """
    corrections = {}
    correction_fields = [
        "name",
        "wine_type",
        "vintage",
        "country",
        "subregion",
        "grapes",
        "vineyard",
        "abv",
        "size",
        "category",
        "barcode",
        "appellation",
    ]

    for field in correction_fields:
        extracted_value = extracted_data.get(field)
        cleaned_value = cleaned_data.get(field)

        if extracted_value is None or cleaned_value is None:
            continue

        if isinstance(extracted_value, list) and isinstance(cleaned_value, list):
            if set(extracted_value) != set(cleaned_value):
                corrections[field] = str(cleaned_value)
        elif str(extracted_value) != str(cleaned_value):
            corrections[field] = str(cleaned_value)

    return corrections
