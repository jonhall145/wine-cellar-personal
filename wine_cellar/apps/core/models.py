import os

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _


def user_directory_path(instance, filename: str) -> str:
    """Generate upload path for user files."""
    return f"user_{instance.user.pk}/{filename}"


def versioned_media_url(field):
    """Append ?v={mtime} to a media file URL for cache busting."""
    if not field:
        return None
    url = field.url
    try:
        mtime = int(os.path.getmtime(field.path))
        return f"{url}?v={mtime}"
    except (FileNotFoundError, ValueError):
        return url


class UserContentModel(models.Model):
    """Abstract base model for user-owned content."""

    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        null=True,
        verbose_name=_("User"),
    )
    household = models.ForeignKey(
        "household.Household",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_items",
        verbose_name=_("Household"),
    )
    created = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Created"),
    )
    modified = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Modified"),
    )

    class Meta:
        abstract = True
