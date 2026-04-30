import datetime
import logging
import transaction
from PIL import Image

from wine_cellar.apps.whisky.models import (
    Whisky,
    WhiskyBarcode,
    WhiskyImage,
    WhiskyStorageItem,
    ImageType,
    FillLevel,
    VisionExtractionLog,
)
from wine_cellar.apps.whisky.utils import apply_manual_crop

logger = logging.getLogger(__name__)


class WhiskyCreationService:
    """Service for whisky creation and initialization logic."""

    @staticmethod
    @transaction.atomic
    def create_or_update_whisky(user, household, cleaned_data):
        """Create or update a whisky with its related objects.
        
        Returns:
            (whisky, created) tuple
        """
        abv = cleaned_data["abv"]
        size = cleaned_data["size"]
        barcode = cleaned_data.get("barcode")
        comment = cleaned_data["comment"]
        country = cleaned_data["country"]
        price = cleaned_data["price"]
        name = cleaned_data["name"]
        rating = cleaned_data["rating"]
        whisky_type = cleaned_data["whisky_type"]
        distillery = cleaned_data.get("distillery")
        region = cleaned_data.get("region")
        age_statement = cleaned_data.get("age_statement")
        vintage_year = cleaned_data.get("vintage_year")
        bottled_year = cleaned_data.get("bottled_year")
        peated_level = cleaned_data.get("peated_level") or None
        cask_type = cleaned_data.get("cask_type") or ""
        cask_strength = cleaned_data.get("cask_strength", False)
        color = cleaned_data.get("color")
        bottler = cleaned_data.get("bottler")
        bottler_series = cleaned_data.get("bottler_series")
        cask_number = cleaned_data.get("cask_number")
        batch_number = cleaned_data.get("batch_number")
        bottle_number = cleaned_data.get("bottle_number")
        limited_edition = cleaned_data.get("limited_edition", False)
        release_year = cleaned_data.get("release_year")
        source = cleaned_data.get("source")
        owner = cleaned_data.get("owner", "")

        whisky, created = Whisky.objects.get_or_create(
            name=name,
            whisky_type=whisky_type,
            abv=abv,
            size=size,
            vintage_year=vintage_year,
            bottled_year=bottled_year,
            user=user,
            household=household,
            deleted=False,
            defaults={
                "distillery": distillery,
                "region": region,
                "country": country,
                "age_statement": age_statement,
                "peated_level": peated_level,
                "cask_type": cask_type,
                "cask_strength": cask_strength,
                "color": color,
                "bottler": bottler,
                "bottler_series": bottler_series,
                "cask_number": cask_number,
                "batch_number": batch_number,
                "bottle_number": bottle_number,
                "limited_edition": limited_edition,
                "release_year": release_year,
                "comment": comment,
                "rating": rating,
                "price": price,
                "source": source,
                "owner": owner,
            },
        )

        if barcode:
            WhiskyBarcode.objects.get_or_create(
                barcode=barcode,
                user=user,
                defaults={"whisky": whisky, "household": household},
            )

        storage = cleaned_data.get("storage")
        if storage:
            row = cleaned_data.get("row")
            column = cleaned_data.get("column")
            bottle_price = cleaned_data.get("bottle_price") or price
            is_gift = cleaned_data.get("is_gift", False)
            gift_from = cleaned_data.get("gift_from")
            occasion = cleaned_data.get("occasion")
            fill_level = cleaned_data.get("fill_level", FillLevel.UNOPENED)
            dreg_date = datetime.date.today() if fill_level == FillLevel.DREG else None
            WhiskyStorageItem.objects.create(
                storage=storage,
                whisky=whisky,
                row=row,
                column=column,
                user=user,
                household=household,
                price=bottle_price,
                is_gift=is_gift,
                gift_from=gift_from,
                occasion=occasion,
                fill_level=fill_level,
                dreg_date=dreg_date,
            )

        return whisky, created

    @staticmethod
    def create_whisky_images(whisky, user, cleaned_data, image_fields_map):
        """Create WhiskyImage records from form data.
        
        Args:
            whisky: Whisky instance
            user: User instance
            cleaned_data: Form cleaned_data dict
            image_fields_map: Dict mapping field names to ImageType values
        """
        for field_name, image_type in image_fields_map.items():
            image = cleaned_data.get(field_name)
            if not image:
                continue

            WhiskyImage.objects.get_or_create(
                whisky=whisky,
                image=image,
                user=user,
                image_type=image_type,
            )

    @staticmethod
    def apply_auto_crop_from_extraction(whisky, extracted_data):
        """Apply AI-extracted label bounds as auto-crop thumbnails.
        
        Args:
            whisky: Whisky instance
            extracted_data: Dict of extraction results with label_bounds_front/back
        """
        bounds_map = {
            ImageType.LABEL_FRONT: extracted_data.get("label_bounds_front"),
            ImageType.LABEL_BACK: extracted_data.get("label_bounds_back"),
        }

        for image_type, bounds in bounds_map.items():
            if not bounds:
                continue
            whisky_image = whisky.whiskeyimage_set.filter(image_type=image_type).first()
            if not whisky_image or not whisky_image.image:
                continue
            try:
                import os
                from django.conf import settings as django_settings

                full_path = os.path.join(
                    django_settings.MEDIA_ROOT, whisky_image.image.name
                )
                with Image.open(full_path) as img:
                    img_width, img_height = img.size

                x = int((bounds["x1"] / 100) * img_width)
                y = int((bounds["y1"] / 100) * img_height)
                width = int(((bounds["x2"] - bounds["x1"]) / 100) * img_width)
                height = int(((bounds["y2"] - bounds["y1"]) / 100) * img_height)

                if width > 0 and height > 0:
                    thumb_path = apply_manual_crop(whisky_image, x, y, width, height)
                    whisky_image.thumbnail = thumb_path
                    whisky_image.save(update_fields=["thumbnail"])
            except Exception:
                logger.exception(
                    f"Auto-crop failed for whisky {whisky.pk} image type {image_type}"
                )

    @staticmethod
    def link_extraction_log(whisky, user, cleaned_data, extraction_result):
        """Link vision extraction log to created whisky and record corrections.
        
        Args:
            whisky: Whisky instance
            user: User instance
            cleaned_data: Form cleaned_data dict
            extraction_result: Dict of extraction results
        """
        try:
            log = (
                VisionExtractionLog.objects.filter(
                    user=user,
                    whisky__isnull=True,
                )
                .order_by("-created")
                .first()
            )
            if log:
                corrections = _detect_corrections(cleaned_data,
                                                 extraction_result.get("extracted_data", {}))
                log.whisky = whisky
                log.was_successful = True
                if corrections:
                    log.user_corrections = corrections
                log.save(
                    update_fields=[
                        "whisky",
                        "was_successful",
                        "user_corrections",
                    ]
                )
        except Exception:
            logger.exception(
                "Failed to link extraction log to whisky %s", whisky.pk
            )


def _detect_corrections(cleaned_data, extracted_data):
    """Detect differences between extracted data and user-corrected values.
    
    Returns a dict of fields that were different from extraction.
    """
    corrections = {}
    correction_fields = [
        "name",
        "whisky_type",
        "distillery",
        "region",
        "country",
        "age_statement",
        "vintage_year",
        "bottled_year",
        "abv",
        "size",
        "peated_level",
        "cask_type",
        "color",
        "bottler",
        "barcode",
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
