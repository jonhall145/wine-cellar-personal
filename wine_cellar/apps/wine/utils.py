import os
from typing import TYPE_CHECKING

from django.conf import settings
from PIL import ExifTags, Image

if TYPE_CHECKING:
    from wine_cellar.apps.wine.models import WineImage


def user_directory_path(instance: "WineImage", filename: str) -> str:
    """Generate upload path for user files."""
    return f"user_{instance.user.pk}/{filename}"


def make_thumbnail(instance: "WineImage", height: int = 225) -> str:
    """
    Creates a proportional thumbnail with given height.
    Returns the path to the thumbnail file.
    """
    image_path = instance.image.name
    full_path = os.path.join(settings.MEDIA_ROOT, image_path)
    img = Image.open(full_path)

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

    aspect = img.width / img.height
    width = int(height * aspect)

    img.thumbnail((width, height), Image.LANCZOS)
    base, ext = os.path.splitext(image_path)
    name = f"{base}_thumb{ext}"
    thumb_full_path = os.path.join(settings.MEDIA_ROOT, name)

    img.save(thumb_full_path, format=img.format, quality=100)
    return name
