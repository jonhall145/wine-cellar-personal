import os

import pytest
from PIL import Image

from wine_cellar.apps.wine.utils import apply_manual_crop, make_thumbnail


def _create_test_image(path: str, size=(400, 300)) -> None:
    image = Image.new("RGB", size, color="blue")
    image.save(path, format="JPEG")


@pytest.mark.django_db
def test_make_thumbnail_creates_file(user, wine_factory, wine_image_factory, settings):
    wine = wine_factory(user=user)
    wine_image = wine_image_factory(user=user, wine=wine)
    image_path = os.path.join(settings.MEDIA_ROOT, wine_image.image.name)
    _create_test_image(image_path)

    thumb_name = make_thumbnail(wine_image)

    thumb_path = os.path.join(settings.MEDIA_ROOT, thumb_name)
    assert os.path.exists(thumb_path)


@pytest.mark.django_db
def test_apply_manual_crop_creates_thumbnail(
    user, wine_factory, wine_image_factory, settings
):
    wine = wine_factory(user=user)
    wine_image = wine_image_factory(user=user, wine=wine)
    image_path = os.path.join(settings.MEDIA_ROOT, wine_image.image.name)
    _create_test_image(image_path, size=(500, 400))

    thumb_name = apply_manual_crop(wine_image, x=10, y=10, width=200, height=150)

    thumb_path = os.path.join(settings.MEDIA_ROOT, thumb_name)
    assert os.path.exists(thumb_path)
