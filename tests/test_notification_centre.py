from datetime import timedelta
from http import HTTPStatus

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertTemplateUsed

from wine_cellar.apps.household.models import HouseholdInvitation, HouseholdRole
from wine_cellar.apps.user.models import InAppNotificationStatus, NotificationChannel
from wine_cellar.apps.user.views import get_user_settings
from wine_cellar.apps.wine.models import ReorderReminder


@pytest.mark.django_db
def test_notifications_view_combines_drink_low_stock_and_invitation(
    client, user, wine_factory, storage_item_factory
):
    client.force_login(user)
    current_year = timezone.now().year
    wine = wine_factory(user=user, drink_to=current_year)
    storage = user.storage_set.first()
    storage_item_factory(wine=wine, storage=storage, user=user)
    ReorderReminder.objects.create(
        wine=wine,
        user=user,
        household=user.user_settings.active_household,
        min_stock=1,
        is_active=True,
    )
    HouseholdInvitation.objects.create(
        household=user.user_settings.active_household,
        email=user.email,
        role=HouseholdRole.MEMBER,
        invited_by=user,
    )

    response = client.get(reverse("notifications"))

    assert response.status_code == HTTPStatus.OK
    assertTemplateUsed(response, "core/notifications.html")
    assert response.context["notification_unread_count"] == 3
    assert set(response.context["notification_sections"]) == {
        "Drink window",
        "Low stock",
        "Household invitations",
    }


@pytest.mark.django_db
def test_notifications_view_respects_in_app_preferences(
    client, user, wine_factory, storage_item_factory
):
    client.force_login(user)
    user_settings = get_user_settings(user)
    user_settings.low_stock_notifications = NotificationChannel.EMAIL
    user_settings.save()

    wine = wine_factory(user=user)
    storage = user.storage_set.first()
    storage_item_factory(wine=wine, storage=storage, user=user)
    ReorderReminder.objects.create(
        wine=wine,
        user=user,
        household=user.user_settings.active_household,
        min_stock=1,
        is_active=True,
    )

    response = client.get(reverse("notifications"))

    assert response.status_code == HTTPStatus.OK
    assert "Low stock" not in response.context["notification_sections"]


@pytest.mark.django_db
def test_notifications_view_includes_one_day_and_one_week_occasion_dates(
    client, user, wine_factory, storage_item_factory
):
    client.force_login(user)
    today = timezone.localdate()
    storage = user.storage_set.first()
    tomorrow = wine_factory(user=user, name="Tomorrow Wine")
    next_week = wine_factory(user=user, name="Next Week Wine")
    later = wine_factory(user=user, name="Later Wine")
    deleted_wine = wine_factory(user=user, name="Deleted Wine")
    deleted_wine.deleted = True
    deleted_wine.save(update_fields=["deleted"])
    storage_item_factory(
        wine=tomorrow,
        storage=storage,
        user=user,
        occasion="Birthday",
        occasion_date=today + timedelta(days=1),
    )
    storage_item_factory(
        wine=next_week,
        storage=storage,
        user=user,
        occasion="Anniversary",
        occasion_date=today + timedelta(weeks=1),
    )
    storage_item_factory(
        wine=later,
        storage=storage,
        user=user,
        occasion_date=today + timedelta(days=2),
    )
    storage_item_factory(
        wine=deleted_wine,
        storage=storage,
        user=user,
        occasion_date=today + timedelta(weeks=1),
    )

    response = client.get(reverse("notifications"))

    occasion_notifications = response.context["notification_sections"]["Occasions"]
    assert {notification.title for notification in occasion_notifications} == {
        "Tomorrow Wine",
        "Next Week Wine",
    }
    assert {
        notification.notification_type for notification in occasion_notifications
    } == {"occasion_date"}
    assert {notification.body for notification in occasion_notifications} == {
        "Birthday is tomorrow.",
        "Anniversary is one week.",
    }
    assert {
        notification.key.rsplit(":", maxsplit=1)[-1]
        for notification in occasion_notifications
    } == {"tomorrow", "one week"}


@pytest.mark.django_db
@override_settings(CELLAR_APP_TYPE="whisky")
def test_whisky_notifications_skip_wine_occasion_routes(
    user, wine_factory, storage_item_factory, monkeypatch
):
    from wine_cellar.apps.user.notifications import build_in_app_notifications

    wine = wine_factory(user=user)
    storage_item_factory(
        wine=wine,
        storage=user.storage_set.first(),
        user=user,
        occasion_date=timezone.localdate() + timedelta(days=1),
    )

    def reject_wine_route(route_name, *args, **kwargs):
        if route_name == "wine-detail":
            raise AssertionError("Whisky notifications must not reverse wine routes")
        return route_name

    monkeypatch.setattr(
        "wine_cellar.apps.user.notifications.reverse", reject_wine_route
    )

    notifications = build_in_app_notifications(user)

    assert not any(item.notification_type == "occasion_date" for item in notifications)


@pytest.mark.django_db
def test_occasion_date_notifications_respect_in_app_preferences(
    client, user, wine_factory, storage_item_factory
):
    client.force_login(user)
    user_settings = get_user_settings(user)
    user_settings.drink_window_notifications = NotificationChannel.EMAIL
    user_settings.save()
    wine = wine_factory(user=user)
    storage_item_factory(
        wine=wine,
        storage=user.storage_set.first(),
        user=user,
        occasion_date=timezone.localdate() + timedelta(days=1),
    )

    response = client.get(reverse("notifications"))

    assert "Occasions" not in response.context["notification_sections"]


@pytest.mark.django_db
def test_notification_mark_read_and_dismiss(
    client, user, wine_factory, storage_item_factory
):
    client.force_login(user)
    wine = wine_factory(user=user)
    storage = user.storage_set.first()
    storage_item_factory(wine=wine, storage=storage, user=user)
    reminder = ReorderReminder.objects.create(
        wine=wine,
        user=user,
        household=user.user_settings.active_household,
        min_stock=1,
        is_active=True,
    )
    notification_key = f"low-stock:wine:{reminder.pk}:1"

    response = client.post(
        reverse("notification-mark-read"),
        data={
            "notification_key": notification_key,
            "notification_type": "low_stock",
            "next": reverse("notifications"),
        },
    )

    assert response.status_code == HTTPStatus.FOUND
    status = InAppNotificationStatus.objects.get(
        user=user,
        notification_key=notification_key,
    )
    assert status.is_read is True

    response = client.post(
        reverse("notification-dismiss"),
        data={
            "notification_key": notification_key,
            "notification_type": "low_stock",
            "next": reverse("notifications"),
        },
    )

    assert response.status_code == HTTPStatus.FOUND
    status.refresh_from_db()
    assert status.dismissed_at is not None


@pytest.mark.django_db
def test_notification_status_update_rejects_external_redirect(client, user):
    client.force_login(user)

    response = client.post(
        reverse("notification-mark-read"),
        data={
            "notification_key": "low-stock:wine:1:1",
            "notification_type": "low_stock",
            "next": "https://attacker.example/",
        },
    )

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("notifications")
