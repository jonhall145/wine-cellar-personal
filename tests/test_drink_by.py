from datetime import date, timedelta

import pytest
from django.core import mail
from django.utils import timezone

from wine_cellar.apps.storage.models import StorageItem
from wine_cellar.apps.user.models import NotificationChannel
from wine_cellar.apps.user.views import get_user_settings
from wine_cellar.apps.wine.management.commands.send_drink_reminders import (
    drink_by_reminder,
)
from wine_cellar.apps.wine.models import Wine
from wine_cellar.apps.wine.services import WineReminderService


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


@pytest.mark.django_db
def test_drink_by_reminder_skips_email_for_in_app_only(user, wine_factory):
    user_settings = get_user_settings(user)
    user_settings.drink_window_notifications = NotificationChannel.IN_APP
    user_settings.save()
    current_year = timezone.now().year
    wine = wine_factory(drink_to=current_year, user=user)
    storage = user.storage_set.first()
    StorageItem.objects.create(wine=wine, storage=storage, user=user)

    drink_by_reminder()

    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_occasion_date_reminder_sends_single_email_with_due_bottles(
    user, wine_factory, monkeypatch
):
    today = date(2026, 8, 10)
    monkeypatch.setattr(
        "wine_cellar.apps.wine.services.reminders.timezone.localdate",
        lambda: today,
    )
    storage = user.storage_set.first()
    household = user.user_settings.active_household
    one_month = wine_factory(user=user, name="Month Wine")
    one_week = wine_factory(user=user, name="Week Wine")
    one_day = wine_factory(user=user, name="Day Wine")
    ignored = wine_factory(user=user, name="Ignored Wine")
    StorageItem.objects.create(
        wine=one_month,
        storage=storage,
        user=user,
        household=household,
        occasion_date=date(2026, 9, 10),
    )
    StorageItem.objects.create(
        wine=one_week,
        storage=storage,
        user=user,
        household=household,
        occasion_date=today + timedelta(weeks=1),
    )
    StorageItem.objects.create(
        wine=one_day,
        storage=storage,
        user=user,
        household=household,
        occasion_date=today + timedelta(days=1),
    )
    StorageItem.objects.create(
        wine=ignored,
        storage=storage,
        user=user,
        household=household,
        occasion_date=today + timedelta(days=2),
    )

    sent = WineReminderService.send_occasion_date_reminders()

    assert sent == 1
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [user.email]
    assert "Month Wine" in mail.outbox[0].body
    assert "Week Wine" in mail.outbox[0].body
    assert "Day Wine" in mail.outbox[0].body
    assert "Ignored Wine" not in mail.outbox[0].body


@pytest.mark.django_db
def test_occasion_date_reminder_respects_email_delivery_preference(
    user, wine_factory, monkeypatch
):
    today = date(2026, 8, 10)
    monkeypatch.setattr(
        "wine_cellar.apps.wine.services.reminders.timezone.localdate",
        lambda: today,
    )
    user_settings = get_user_settings(user)
    user_settings.drink_window_notifications = NotificationChannel.IN_APP
    user_settings.save()
    wine = wine_factory(user=user)
    StorageItem.objects.create(
        wine=wine,
        storage=user.storage_set.first(),
        user=user,
        household=user.user_settings.active_household,
        occasion_date=today + timedelta(days=1),
    )

    sent = WineReminderService.send_occasion_date_reminders()

    assert sent == 0
    assert len(mail.outbox) == 0
