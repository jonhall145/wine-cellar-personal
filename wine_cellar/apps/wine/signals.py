from typing import Any

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from wine_cellar.apps.wine.models import Wine, WineImage
from wine_cellar.apps.wine.utils import make_thumbnail


@receiver(post_save, sender=WineImage)
def generate_thumbnail(
    sender: type[WineImage], instance: WineImage, **kwargs: Any
) -> None:
    """Generate thumbnail for wine images after save."""
    if instance.image and not instance.thumbnail:
        thumb_name = make_thumbnail(instance)
        instance.thumbnail.name = thumb_name
        instance.save(update_fields=["thumbnail"])


def _invalidate_homepage_cache(instance: Any) -> None:
    """Clear homepage stats cache for the instance's household."""
    household_id = getattr(instance, "household_id", None)
    if household_id:
        cache.delete(f"homepage_stats_{household_id}")


@receiver(post_save, sender=Wine)
@receiver(post_delete, sender=Wine)
def invalidate_homepage_on_wine_change(
    sender: type, instance: Wine, **kwargs: Any
) -> None:
    _invalidate_homepage_cache(instance)


@receiver(post_save, sender="storage.StorageItem")
@receiver(post_delete, sender="storage.StorageItem")
def invalidate_homepage_on_stock_change(
    sender: type, instance: Any, **kwargs: Any
) -> None:
    _invalidate_homepage_cache(instance)
