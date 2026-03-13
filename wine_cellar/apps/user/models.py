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
    active_household = models.ForeignKey(
        "household.Household",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="active_for_users",
        verbose_name=_("Active Household"),
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
    reminder_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Drink Window Reminders"),
        help_text=_("Receive reminders when wines approach their drink-by date"),
    )
    reminder_years_before = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Years Before Drink-By"),
        help_text=_(
            "How many years before the drink-by date to start reminding"
            " (0 = in the year itself)"
        ),
    )

    class Meta:
        verbose_name = _("User Settings")
        verbose_name_plural = _("User Settings")

    def __str__(self):
        return f"Settings for {self.user}"


class PushSubscription(models.Model):
    """Web Push API subscription for a user's browser."""

    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
        verbose_name=_("User"),
    )
    endpoint = models.URLField(max_length=500, verbose_name=_("Endpoint"))
    p256dh = models.CharField(max_length=200, verbose_name=_("p256dh Key"))
    auth = models.CharField(max_length=200, verbose_name=_("Auth Key"))
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("Created"))

    class Meta:
        verbose_name = _("Push Subscription")
        verbose_name_plural = _("Push Subscriptions")
        unique_together = ("user", "endpoint")

    def __str__(self):
        return f"Push subscription for {self.user} ({self.endpoint[:50]}...)"

    def to_webpush_dict(self):
        """Return dict in the format pywebpush expects."""
        return {
            "endpoint": self.endpoint,
            "keys": {
                "p256dh": self.p256dh,
                "auth": self.auth,
            },
        }
