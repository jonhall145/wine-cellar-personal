import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.wine.emails import send_drink_by_reminder
from wine_cellar.apps.wine.models import Wine

logger = logging.getLogger(__name__)


@shared_task(name="drink_by_reminder")
def drink_by_reminder():
    """Send reminders for wines in their final drinking year."""
    User = get_user_model()
    users = (
        User.objects.exclude(email__isnull=True)
        .exclude(email__exact="")
        .exclude(user_settings__notifications=False)
    )
    current_year = timezone.now().year
    for user in users:
        # Get the user's active household
        household = get_active_household(user)
        if not household:
            continue
        # Find wines where drink_to matches current year (not "now" which is 0)
        wines = Wine.objects.filter(
            household=household,
            drink_to=current_year,
            storageitem__isnull=False,
            storageitem__deleted=False,
        ).distinct()
        if wines.count() > 0:
            send_drink_by_reminder(user, wines)
