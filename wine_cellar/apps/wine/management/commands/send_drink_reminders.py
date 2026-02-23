import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.wine.emails import send_drink_by_reminder
from wine_cellar.apps.wine.models import Wine

logger = logging.getLogger(__name__)


def drink_by_reminder():
    """Send reminders for wines in their final drinking year."""
    User = get_user_model()
    users = (
        User.objects.exclude(email__isnull=True)
        .exclude(email__exact="")
        .exclude(user_settings__notifications=False)
    )
    current_year = timezone.now().year
    sent = 0
    for user in users:
        household = get_active_household(user)
        if not household:
            continue
        wines = Wine.objects.filter(
            household=household,
            drink_to=current_year,
            storageitem__isnull=False,
            storageitem__deleted=False,
        ).distinct()
        if wines.count() > 0:
            send_drink_by_reminder(user, wines)
            sent += 1
            logger.info(
                "Sent drink-by reminder to %s (%d wines)",
                user.email,
                wines.count(),
            )
    return sent


class Command(BaseCommand):
    help = "Send email reminders for wines in their final drinking year."

    def handle(self, *args, **options):
        sent = drink_by_reminder()
        self.stdout.write(f"Sent {sent} reminder(s)")
