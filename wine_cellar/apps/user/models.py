from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserSettings(models.Model):
    user = models.OneToOneField(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="user_settings",
        verbose_name=_("User"),
    )
    language = models.CharField(
        max_length=7,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE,
        verbose_name=_("Language"),
    )
    currency = models.CharField(
        max_length=3,
        choices=settings.CURRENCIES,
        default="EUR",
        verbose_name=_("Currency"),
    )
    notifications = models.BooleanField(
        default=True,
        verbose_name=_("Notifications"),
    )

    class Meta:
        verbose_name = _("User Settings")
        verbose_name_plural = _("User Settings")

    def __str__(self):
        return f"Settings for {self.user}"
