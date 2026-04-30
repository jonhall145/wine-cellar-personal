import datetime
from http import HTTPStatus

import pytest
from django.urls import reverse

from wine_cellar.apps.storage.models import Storage
from wine_cellar.apps.whisky.models import WhiskyReorderReminder, WhiskyStorageItem


@pytest.mark.django_db
def test_notifications_view_shows_whisky_dreg_and_low_stock(
    client, user, whisky_factory
):
    client.force_login(user)
    household = user.user_settings.active_household
    storage = Storage.objects.create(
        user=user,
        household=household,
        name="Whisky Shelf",
        app_type="whisky",
    )
    whisky = whisky_factory(user=user, household=household)
    WhiskyStorageItem.objects.create(
        user=user,
        household=household,
        storage=storage,
        whisky=whisky,
        fill_level="DR",
        dreg_date=datetime.date.today() - datetime.timedelta(days=350),
    )
    WhiskyReorderReminder.objects.create(
        user=user,
        household=household,
        whisky=whisky,
        min_stock=1,
        is_active=True,
    )

    response = client.get(reverse("notifications"))

    assert response.status_code == HTTPStatus.OK
    assert response.context["notification_unread_count"] == 2
    assert set(response.context["notification_sections"]) == {
        "Drink window",
        "Low stock",
    }
