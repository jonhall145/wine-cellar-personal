from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from wine_cellar.apps.wine.emails import send_drink_by_reminder
from wine_cellar.apps.wine.models import Wine


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
        # Find wines where drink_to matches current year (not "now" which is 0)
        wines = Wine.objects.filter(
            user=user,
            drink_to=current_year,
            storageitem__isnull=False,
            storageitem__deleted=False,
        ).distinct()
        if wines.count() > 0:
            send_drink_by_reminder(user, wines)
