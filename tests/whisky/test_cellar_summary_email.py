import datetime
from decimal import Decimal
from io import StringIO

import pytest
from django.core import mail
from django.core.management import call_command

from wine_cellar.apps.whisky.models import (
    FillLevel,
    WhiskyDrinkingWindowAlert,
    WhiskyDrinkRecord,
    WhiskyReorderReminder,
    WhiskyWishlist,
)


@pytest.mark.django_db
def test_send_cellar_summary_includes_whisky_stats(
    user, whisky_factory, whisky_storage_item_factory
):
    household = user.user_settings.active_household
    whisky = whisky_factory(
        user=user,
        household=household,
        name="Lagavulin 16",
        price=Decimal("79.00"),
    )
    storage_item = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky=whisky,
        price=Decimal("82.00"),
        fill_level=FillLevel.DREG,
        dreg_date=datetime.date.today() - datetime.timedelta(days=340),
    )
    WhiskyDrinkRecord.objects.create(
        whisky=whisky,
        storage_item=storage_item,
        user=user,
        household=household,
        date_consumed=datetime.date.today(),
        rating=2,
    )
    WhiskyReorderReminder.objects.create(
        whisky=whisky,
        user=user,
        household=household,
        min_stock=1,
    )
    WhiskyWishlist.objects.create(
        name="Ardbeg Uigeadail",
        user=user,
        household=household,
    )
    WhiskyDrinkingWindowAlert.objects.create(
        whisky=whisky,
        user=user,
        household=household,
        alert_date=datetime.date.today() + datetime.timedelta(days=7),
        message="Best before the summer.",
        is_read=False,
    )

    stdout = StringIO()
    call_command("send_cellar_summary", period="monthly", stdout=stdout)

    assert stdout.getvalue().strip() == "Sent 1 monthly summary email(s)"
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.subject == "Monthly Whisky Cabinet Summary"
    assert "Whiskies tracked: 1" in message.body
    assert "Bottles in stock: 1" in message.body
    assert "Open bottles: 1" in message.body
    assert "Dreg warnings: 1" in message.body
    assert "Upcoming drinking window alerts (1)" in message.body
    assert "Lagavulin 16" in message.body
    assert "Best before the summer." in message.body
