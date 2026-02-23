import pytest
from django.core import mail
from django.utils import timezone

from wine_cellar.apps.storage.models import StorageItem
from wine_cellar.apps.user.views import get_user_settings
from wine_cellar.apps.wine.management.commands.send_drink_reminders import (
    drink_by_reminder,
)
from wine_cellar.apps.wine.models import Wine


@pytest.mark.django_db
def test_drink_by_reminder(user, wine_factory):
    """Test that reminder is sent for wines with drink_to matching current year."""
    current_year = timezone.now().year
    # Wine with drink_to this year should trigger reminder
    wine = wine_factory(drink_to=current_year, user=user)
    # Wine with drink_to next year should not trigger reminder
    wine_1 = wine_factory(drink_to=current_year + 1, user=user)
    storage = user.storage_set.first()
    StorageItem.objects.create(wine=wine, storage=storage, user=user)
    StorageItem.objects.create(wine=wine_1, storage=storage, user=user)
    drink_by_reminder()
    assert Wine.objects.count() == 2
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_drink_by_reminder_not_send_if_notifications_disabled(user, wine_factory):
    user_settings = get_user_settings(user)
    user_settings.notifications = False
    user_settings.save()
    current_year = timezone.now().year
    wine = wine_factory(drink_to=current_year, user=user)
    wine_1 = wine_factory(drink_to=current_year + 1, user=user)
    storage = user.storage_set.first()
    StorageItem.objects.create(wine=wine, storage=storage, user=user)
    StorageItem.objects.create(wine=wine_1, storage=storage, user=user)
    drink_by_reminder()
    assert Wine.objects.count() == 2
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_drink_by_reminder_not_send_for_other_user(user, user_factory, wine_factory):
    current_year = timezone.now().year
    user1 = user_factory(email="user1@example.org")
    # user1 has wine with drink_to this year
    wine = wine_factory(drink_to=current_year, user=user1)
    # main user has wine with drink_to next year (no reminder)
    wine_1 = wine_factory(drink_to=current_year + 1, user=user)
    storage = user.storage_set.first()
    storage_1 = user1.storage_set.first()
    StorageItem.objects.create(wine=wine, storage=storage_1, user=user1)
    StorageItem.objects.create(wine=wine_1, storage=storage, user=user)
    drink_by_reminder()
    assert Wine.objects.count() == 2
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [user1.email]
