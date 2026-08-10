import logging

from django.core.management.base import BaseCommand

from wine_cellar.apps.wine.services import WineReminderService

logger = logging.getLogger(__name__)


def drink_by_reminder() -> int:
    """Send reminders for wines approaching drink-by and occasion dates.

    Sends both email and push notifications. Respects per-user preferences:
    - reminder_enabled: whether to send reminders at all
    - reminder_years_before: how many years before drink_to to start reminding
    """
    sent = (
        WineReminderService.send_drink_by_reminders()
        + WineReminderService.send_occasion_date_reminders()
    )
    logger.info("Sent %d wine reminder batch(es)", sent)
    return sent


class Command(BaseCommand):
    help = "Send email reminders for wine drinking windows and occasion dates."

    def handle(self, *args, **options):
        sent = drink_by_reminder()
        self.stdout.write(f"Sent {sent} reminder(s)")
