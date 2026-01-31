import logging
import os
from typing import TYPE_CHECKING

from django.conf import settings
from PIL import ExifTags, Image

if TYPE_CHECKING:
    from wine_cellar.apps.wine.models import WineImage

logger = logging.getLogger(__name__)


def user_directory_path(instance: "WineImage", filename: str) -> str:
    """Generate upload path for user files."""
    return f"user_{instance.user.pk}/{filename}"


def correct_image_orientation(img: Image.Image) -> Image.Image:
    """Apply EXIF orientation correction to image."""
    try:
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == "Orientation":
                break
        exif = img._getexif()
        if exif:
            orientation_value = exif.get(orientation)
            if orientation_value == 3:
                img = img.rotate(180, expand=True)
            elif orientation_value == 6:
                img = img.rotate(270, expand=True)
            elif orientation_value == 8:
                img = img.rotate(90, expand=True)
    except (AttributeError, KeyError, IndexError):
        # Image has no EXIF or orientation info
        pass
    return img


def apply_manual_crop(
    instance: "WineImage", x: int, y: int, width: int, height: int
) -> str:
    """
    Apply manual crop coordinates to an image and save as new thumbnail.

    Args:
        instance: WineImage model instance
        x, y: Top-left corner of crop area
        width, height: Size of crop area

    Returns:
        Path to the cropped thumbnail file
    """
    image_path = instance.image.name
    full_path = os.path.join(settings.MEDIA_ROOT, image_path)
    img = Image.open(full_path)

    # Convert to RGB if necessary
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # Correct EXIF orientation first
    img = correct_image_orientation(img)

    # Store original format
    original_format = img.format

    # Crop the image
    crop_box = (x, y, x + width, y + height)
    cropped_img = img.crop(crop_box)

    # Resize to standard thumbnail height (225px) while maintaining aspect
    target_height = 225
    aspect = cropped_img.width / cropped_img.height
    target_width = int(target_height * aspect)
    result_img = cropped_img.resize((target_width, target_height), Image.LANCZOS)

    # Save thumbnail
    base, ext = os.path.splitext(image_path)
    name = f"{base}_thumb{ext}"
    thumb_full_path = os.path.join(settings.MEDIA_ROOT, name)

    # Determine format
    save_format = original_format
    if save_format is None or save_format.upper() == "MPO":
        save_format = "JPEG" if ext.lower() in (".jpg", ".jpeg") else "PNG"

    result_img.save(thumb_full_path, format=save_format, quality=95)
    return name


def make_thumbnail(instance: "WineImage", height: int = 225) -> str:
    """
    Creates a smart thumbnail with label detection, falling back to
    proportional scaling if detection fails.

    Returns the path to the thumbnail file.
    """
    image_path = instance.image.name
    full_path = os.path.join(settings.MEDIA_ROOT, image_path)
    img = Image.open(full_path)

    # Convert to RGB if necessary (handles RGBA, P mode, etc.)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # Correct EXIF orientation first
    img = correct_image_orientation(img)

    # Store original format before any processing
    original_format = img.format

    # Attempt smart label detection
    try:
        from wine_cellar.apps.wine.label_detection import (
            detect_and_crop_label,
            enhance_detection_for_difficult_images,
        )

        result_img, success = detect_and_crop_label(img, target_height=height)

        # If initial detection failed, try with enhanced image
        if not success:
            enhanced_img = enhance_detection_for_difficult_images(img)
            result_img, success = detect_and_crop_label(
                enhanced_img,
                target_height=height,
            )

            # If still failed, use simple scaling as final fallback
            if not success:
                logger.info("Using simple scaling fallback")
                aspect = img.width / img.height
                width = int(height * aspect)
                result_img = img.copy()
                result_img.thumbnail((width, height), Image.LANCZOS)

    except ImportError:
        # OpenCV not installed - use simple scaling
        logger.warning("OpenCV not available, using simple scaling")
        aspect = img.width / img.height
        width = int(height * aspect)
        result_img = img.copy()
        result_img.thumbnail((width, height), Image.LANCZOS)

    # Save thumbnail
    base, ext = os.path.splitext(image_path)
    name = f"{base}_thumb{ext}"
    thumb_full_path = os.path.join(settings.MEDIA_ROOT, name)

    # Determine format (handle JPEG extension variations)
    save_format = original_format
    if save_format is None or save_format.upper() == "MPO":
        save_format = "JPEG" if ext.lower() in (".jpg", ".jpeg") else "PNG"

    result_img.save(thumb_full_path, format=save_format, quality=95)
    return name
