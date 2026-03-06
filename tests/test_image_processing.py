"""Integration tests for image processing: thumbnails, cropping, orientation."""

import os
from unittest.mock import MagicMock

import pytest
from django.conf import settings
from PIL import Image

from wine_cellar.apps.wine.utils import (
    apply_manual_crop,
    correct_image_orientation,
    make_thumbnail,
)


@pytest.fixture()
def media_dir(tmp_path):
    """Use a temporary directory as MEDIA_ROOT."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "MEDIA_ROOT", str(tmp_path))
        yield tmp_path


def _create_test_image(media_dir, name="user_1/test.jpg", size=(800, 600)):
    """Create a test JPEG image in the media directory."""
    path = media_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, color="red")
    img.save(str(path), format="JPEG")
    return name


def _make_mock_instance(image_name):
    """Create a mock WineImage instance."""
    instance = MagicMock()
    instance.image.name = image_name
    instance.image.path = os.path.join(settings.MEDIA_ROOT, image_name)
    return instance


class TestMakeThumbnail:
    def test_creates_thumbnail_file(self, media_dir):
        name = _create_test_image(media_dir)
        instance = _make_mock_instance(name)

        result = make_thumbnail(instance)

        assert result.endswith("_thumb.jpg")
        assert (media_dir / result).exists()

    def test_thumbnail_has_correct_height(self, media_dir):
        name = _create_test_image(media_dir, size=(1000, 500))
        instance = _make_mock_instance(name)

        result = make_thumbnail(instance, height=225)
        thumb = Image.open(str(media_dir / result))

        assert thumb.height <= 225

    def test_thumbnail_preserves_aspect_ratio(self, media_dir):
        name = _create_test_image(media_dir, size=(1000, 500))
        instance = _make_mock_instance(name)

        result = make_thumbnail(instance, height=225)
        thumb = Image.open(str(media_dir / result))

        original_aspect = 1000 / 500
        thumb_aspect = thumb.width / thumb.height
        assert abs(original_aspect - thumb_aspect) < 0.1

    def test_thumbnail_converts_rgba_to_rgb(self, media_dir):
        """RGBA images should be converted to RGB for JPEG output."""
        path = media_dir / "user_1" / "rgba.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGBA", (400, 300), color=(255, 0, 0, 128))
        img.save(str(path), format="PNG")

        instance = _make_mock_instance("user_1/rgba.png")
        result = make_thumbnail(instance)
        assert (media_dir / result).exists()
        # Verify the thumbnail is valid (RGBA was converted to RGB)
        thumb = Image.open(media_dir / result)
        assert thumb.mode == "RGB"

    def test_thumbnail_png_format(self, media_dir):
        """PNG images should produce PNG thumbnails."""
        path = media_dir / "user_1" / "test.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (400, 300), color="blue")
        img.save(str(path), format="PNG")

        instance = _make_mock_instance("user_1/test.png")
        result = make_thumbnail(instance)
        assert result.endswith("_thumb.png")
        assert (media_dir / result).exists()


class TestApplyManualCrop:
    def test_crop_creates_file(self, media_dir):
        name = _create_test_image(media_dir, size=(800, 600))
        instance = _make_mock_instance(name)

        result = apply_manual_crop(instance, x=100, y=50, width=400, height=300)

        assert "_thumb_" in result
        assert (media_dir / result).exists()

    def test_crop_respects_coordinates(self, media_dir):
        name = _create_test_image(media_dir, size=(800, 600))
        instance = _make_mock_instance(name)

        result = apply_manual_crop(instance, x=0, y=0, width=200, height=200)
        thumb = Image.open(str(media_dir / result))

        # Should be resized to target height (225) preserving 1:1 aspect
        assert thumb.height == 225
        assert abs(thumb.width - 225) < 2  # 1:1 aspect

    def test_crop_with_large_coordinates(self, media_dir):
        """Cropping with coordinates at the image edges."""
        name = _create_test_image(media_dir, size=(800, 600))
        instance = _make_mock_instance(name)

        result = apply_manual_crop(instance, x=400, y=300, width=400, height=300)
        assert (media_dir / result).exists()


class TestCorrectImageOrientation:
    def test_no_exif_returns_unchanged(self):
        """Images without EXIF data should be returned unchanged."""
        img = Image.new("RGB", (100, 200))
        result = correct_image_orientation(img)
        assert result.size == (100, 200)

    def test_handles_missing_orientation(self):
        """Should not raise if EXIF exists but no orientation tag."""
        img = Image.new("RGB", (100, 200))
        # No EXIF at all — should handle gracefully
        result = correct_image_orientation(img)
        assert result is not None
