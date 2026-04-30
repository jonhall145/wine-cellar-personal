import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from wine_cellar.apps.core.push import send_push_to_user
from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.wine.emails import send_drink_by_reminder
from wine_cellar.apps.wine.models import Wine

logger = logging.getLogger(__name__)


def drink_by_reminder() -> int:
    """Send reminders for wines approaching their drink-by year.

    Sends both email and push notifications. Respects per-user preferences:
    - reminder_enabled: whether to send reminders at all
    - reminder_years_before: how many years before drink_to to start reminding
    """
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

        # Get per-user reminder preference (default: 0 years before)
        try:
            years_before = user.user_settings.reminder_years_before
        except UserSettings.DoesNotExist:
            years_before = 0

        # Find wines with drink_to in the reminder window
        max_drink_to = current_year + years_before
        wines = Wine.objects.filter(
            household=household,
            deleted=False,
            drink_to__lte=max_drink_to,
            drink_to__gte=current_year,
            storageitem__isnull=False,
            storageitem__deleted=False,
        ).distinct()
        wine_count = wines.count()
        if wine_count > 0:
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
            logger.info(
                "Sent drink-by reminder to %s (%d wines)",
                user.email or user.username,
                wine_count,
            )
    return sent


class Command(BaseCommand):
    help = "Send email reminders for wines in their final drinking year."

    def handle(self, *args, **options):
        sent = drink_by_reminder()
        self.stdout.write(f"Sent {sent} reminder(s)")
