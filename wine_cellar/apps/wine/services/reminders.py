from calendar import monthrange
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, F, Q
from django.utils import timezone

from wine_cellar.apps.core.push import send_push_to_user
from wine_cellar.apps.storage.models import StorageItem
from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.wine.emails import (
    send_drink_by_reminder,
    send_occasion_date_reminder,
)
from wine_cellar.apps.wine.models import ReorderReminder, Wine


class WineReminderService:
    @staticmethod
    def _one_month_from(value):
        month = value.month % 12 + 1
        year = value.year + (value.month == 12)
        day = min(value.day, monthrange(year, month)[1])
        return value.replace(year=year, month=month, day=day)

    @staticmethod
    def get_reorder_reminders(household):
        return (
            ReorderReminder.objects.filter(household=household, is_active=True)
            .select_related("wine")
            .annotate(
                current_stock=Count(
                    "wine__storageitem",
                    filter=Q(wine__storageitem__deleted=False),
                )
            )
        )

    @classmethod
    def get_reorder_context(cls, household):
        reminders = cls.get_reorder_reminders(household)
        needs_reorder = [
            {
                "wine": reminder.wine,
                "current_stock": reminder.current_stock,
                "min_stock": reminder.min_stock,
                "reminder": reminder,
            }
            for reminder in reminders
            if reminder.current_stock <= reminder.min_stock
        ]
        return reminders, needs_reorder

    @classmethod
    def count_low_stock_reminders(cls, household):
        return (
            cls.get_reorder_reminders(household)
            .filter(current_stock__lte=F("min_stock"))
            .count()
        )

    @staticmethod
    def save_reorder_reminder(*, wine, user, household, min_stock):
        return ReorderReminder.objects.update_or_create(
            wine=wine,
            user=user,
            household=household,
            defaults={"min_stock": min_stock, "is_active": True},
        )

    @staticmethod
    def send_drink_by_reminders() -> int:
        from wine_cellar.apps.user.models import NotificationChannel, UserSettings

        User = get_user_model()
        users = (
            User.objects.exclude(user_settings__notifications=False)
            .exclude(user_settings__reminder_enabled=False)
            .exclude(user_settings__drink_window_notifications=NotificationChannel.NONE)
        )
        current_year = timezone.now().year
        sent = 0

        for user in users:
            household = get_active_household(user)
            if not household:
                continue

            try:
                years_before = user.user_settings.reminder_years_before
            except UserSettings.DoesNotExist:
                years_before = 0

            wines = Wine.objects.filter(
                household=household,
                deleted=False,
                drink_to__lte=current_year + years_before,
                drink_to__gte=current_year,
                storageitem__isnull=False,
                storageitem__deleted=False,
            ).distinct()
            wine_count = wines.count()

            if wine_count <= 0:
                continue

            delivery = getattr(
                user.user_settings,
                "drink_window_notifications",
                NotificationChannel.BOTH,
            )

            if user.email and NotificationChannel.includes_email(delivery):
                send_drink_by_reminder(user, wines)

            if NotificationChannel.includes_in_app(delivery):
                send_push_to_user(
                    user,
                    title="🍷 Drink Window Reminder",
                    body=f"{wine_count} wine(s) are in their drinking window",
                    url="/notifications/",
                )

            sent += 1

        return sent

    @classmethod
    def send_occasion_date_reminders(cls) -> int:
        from wine_cellar.apps.user.models import UserSettings

        User = get_user_model()
        users = (
            User.objects.exclude(user_settings__notifications=False)
            .exclude(user_settings__reminder_enabled=False)
        )
        today = timezone.localdate()
        reminder_dates = {
            cls._one_month_from(today): "one month",
            today + timedelta(weeks=1): "one week",
            today + timedelta(days=1): "one day",
        }
        sent = 0

        for user in users:
            try:
                user_settings = user.user_settings
            except UserSettings.DoesNotExist:
                continue

            if (
                not user.email
                or not user_settings.allows_email_notifications("drink_window")
            ):
                continue

            household = get_active_household(user)
            if not household:
                continue

            bottles = list(
                StorageItem.objects.filter(
                    household=household,
                    deleted=False,
                    occasion_date__in=reminder_dates,
                )
                .select_related("wine", "storage")
                .order_by("occasion_date", "wine__name", "pk")
            )
            if not bottles:
                continue

            for bottle in bottles:
                bottle.occasion_reminder_timing = reminder_dates[bottle.occasion_date]

            send_occasion_date_reminder(user, bottles)
            sent += 1

        return sent
