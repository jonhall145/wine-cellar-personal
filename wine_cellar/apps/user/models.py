from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models

from wine_cellar.apps.core.models import UserContentModel


class NotificationChannel(models.TextChoices):
    NONE = "NO", "None"
    EMAIL = "EM", "Email only"
    IN_APP = "IA", "In-app only"
    BOTH = "BO", "Email and in-app"

    @classmethod
    def includes_email(cls, value):
        return value in {cls.EMAIL, cls.BOTH}

    @classmethod
    def includes_in_app(cls, value):
        return value in {cls.IN_APP, cls.BOTH}


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
        help_text="Global switch for all notification channels.",
    )
    drink_window_notifications = models.CharField(
        max_length=2,
        choices=NotificationChannel.choices,
        default=NotificationChannel.BOTH,
        verbose_name="Drink Window Delivery",
        help_text="Choose how drink window reminders are delivered.",
    )
    low_stock_notifications = models.CharField(
        max_length=2,
        choices=NotificationChannel.choices,
        default=NotificationChannel.IN_APP,
        verbose_name="Low Stock Delivery",
        help_text="Choose how low stock reminders are delivered.",
    )
    household_invitation_notifications = models.CharField(
        max_length=2,
        choices=NotificationChannel.choices,
        default=NotificationChannel.IN_APP,
        verbose_name="Household Invitation Delivery",
        help_text="Choose how household invitations are delivered.",
    )
    price_alert_notifications = models.CharField(
        max_length=2,
        choices=NotificationChannel.choices,
        default=NotificationChannel.NONE,
        verbose_name="Price Alert Delivery",
        help_text="Choose how future price alerts are delivered.",
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

    def get_notification_channel(self, notification_type):
        field_map = {
            "drink_window": "drink_window_notifications",
            "low_stock": "low_stock_notifications",
            "household_invitation": "household_invitation_notifications",
            "price_alert": "price_alert_notifications",
        }
        return getattr(
            self,
            field_map.get(notification_type, "price_alert_notifications"),
            NotificationChannel.NONE,
        )

    def allows_email_notifications(self, notification_type):
        return self.notifications and NotificationChannel.includes_email(
            self.get_notification_channel(notification_type)
        )

    def allows_in_app_notifications(self, notification_type):
        return self.notifications and NotificationChannel.includes_in_app(
            self.get_notification_channel(notification_type)
        )


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


class InAppNotificationStatus(UserContentModel):
    notification_key = models.CharField(max_length=120, verbose_name="Notification Key")
    notification_type = models.CharField(
        max_length=40, verbose_name="Notification Type"
    )
    is_read = models.BooleanField(default=False, verbose_name="Read")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Read At")
    dismissed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Dismissed At",
    )

    class Meta:
        verbose_name = "In-App Notification Status"
        verbose_name_plural = "In-App Notification Statuses"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "notification_key"],
                name="unique_in_app_notification_status",
            )
        ]
        indexes = [
            models.Index(
                fields=["user", "notification_type"],
                name="notif_status_user_type_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.notification_type}"
