from typing import Any

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from wine_cellar.apps.storage.models import Storage, get_app_type

User = get_user_model()


@receiver(post_save, sender=User)
def create_storage(sender: type, instance: Any, created: bool, **kwargs: Any) -> None:
    """Create default storage for new users."""
    if created:
        # Get household from user settings if available
        household = None
        if hasattr(instance, "user_settings") and instance.user_settings:
            household = instance.user_settings.active_household
        app_type = get_app_type()
        Storage.objects.create(
            name="Default Shelf",
            user=instance,
            household=household,
            description="Default storage",
            location="Home",
            rows=0,
            columns=0,
            app_type=app_type,
        )
