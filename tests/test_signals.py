from unittest.mock import patch

import pytest
from django.core.cache import cache

from wine_cellar.apps.wine.models import WineImage


@pytest.mark.django_db
class TestGenerateThumbnail:
    def test_creates_thumbnail_when_image_exists(
        self, user, wine_factory, clear_image_folder
    ):
        wine = wine_factory(user=user)
        with patch("wine_cellar.apps.wine.signals.make_thumbnail") as mock_make_thumb:
            mock_make_thumb.return_value = "thumbs/thumb.jpg"
            img = WineImage(wine=wine, user=user)
            img.image.name = "test_image.jpg"
            img.save()
            mock_make_thumb.assert_called_once_with(img)

    def test_skips_when_thumbnail_already_set(
        self, user, wine_factory, clear_image_folder
    ):
        wine = wine_factory(user=user)
        with patch("wine_cellar.apps.wine.signals.make_thumbnail") as mock_make_thumb:
            # Create image with thumbnail already set to bypass the signal
            img = WineImage(wine=wine, user=user)
            img.image.name = "test_image.jpg"
            img.thumbnail.name = "existing_thumb.jpg"
            img.save()
            mock_make_thumb.assert_not_called()


@pytest.mark.django_db
class TestInvalidateHomepageCache:
    def test_wine_save_clears_cache(self, user, wine_factory):
        wine = wine_factory(user=user)
        cache_key = f"homepage_stats_{wine.household_id}"
        cache.set(cache_key, "cached_data")
        wine.name = "Updated Name"
        wine.save()
        assert cache.get(cache_key) is None

    def test_wine_delete_clears_cache(self, user, wine_factory):
        wine = wine_factory(user=user)
        cache_key = f"homepage_stats_{wine.household_id}"
        cache.set(cache_key, "cached_data")
        wine.delete()
        assert cache.get(cache_key) is None

    def test_stock_save_clears_cache(
        self, user, wine_factory, storage_item_factory, storage_factory
    ):
        storage = storage_factory(user=user)
        wine = wine_factory(user=user)
        household_id = wine.household_id
        cache_key = f"homepage_stats_{household_id}"
        cache.set(cache_key, "cached_data")
        storage_item_factory(storage=storage, wine=wine)
        assert cache.get(cache_key) is None

    def test_stock_delete_clears_cache(
        self, user, wine_factory, storage_item_factory, storage_factory
    ):
        storage = storage_factory(user=user)
        wine = wine_factory(user=user)
        item = storage_item_factory(storage=storage, wine=wine)
        household_id = item.household_id
        cache_key = f"homepage_stats_{household_id}"
        cache.set(cache_key, "cached_data")
        item.delete()
        assert cache.get(cache_key) is None
