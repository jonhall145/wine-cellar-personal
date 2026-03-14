from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models


class UserSettings(models.Model):
    user = models.OneToOneField(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="user_settings",
        verbose_name="User",
    )
    active_household = models.ForeignKey(
        "household.Household",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="active_for_users",
        verbose_name="Active Household",
    )
    currency = models.CharField(
        max_length=3,
        choices=settings.CURRENCIES,
        default="EUR",
        verbose_name="Currency",
    )
    notifications = models.BooleanField(
        default=True,
        verbose_name="Notifications",
    )
    reminder_enabled = models.BooleanField(
        default=True,
        verbose_name="Drink Window Reminders",
        help_text="Receive reminders when wines approach their drink-by date",
    )
    reminder_years_before = models.PositiveIntegerField(
        default=0,
        verbose_name="Years Before Drink-By",
        help_text="How many years before the drink-by date to start reminding"
        " (0 = in the year itself)",
    )

    class Meta:
        verbose_name = "User Settings"
        verbose_name_plural = "User Settings"

    def __str__(self):
        return f"Settings for {self.user}"


class PushSubscription(models.Model):
    """Web Push API subscription for a user's browser."""

    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
        verbose_name="User",
    )
    endpoint = models.URLField(max_length=500, verbose_name="Endpoint")
    p256dh = models.CharField(max_length=200, verbose_name="p256dh Key")
    auth = models.CharField(max_length=200, verbose_name="Auth Key")
    created = models.DateTimeField(auto_now_add=True, verbose_name="Created")

    class Meta:
        verbose_name = "Push Subscription"
        verbose_name_plural = "Push Subscriptions"
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
