from typing import Any

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from wine_cellar.apps.storage.models import Storage

User = get_user_model()


@receiver(post_save, sender=User)
def create_storage(
    sender: type, instance: Any, created: bool, **kwargs: Any
) -> None:
    """Create default storage for new users."""
    if created:
        Storage.objects.create(
            name="Default Shelf",
            user=instance,
            description="Default storage for wines",
            location="Cellar",
            rows=0,
            columns=0,
        )
