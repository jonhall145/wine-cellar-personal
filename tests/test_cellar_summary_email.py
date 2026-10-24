from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core import mail
from django.core.management import call_command

from wine_cellar.apps.storage.models import StorageItem
from wine_cellar.apps.user.views import get_user_settings
from wine_cellar.apps.wine.models import DrinkRecord, ReorderReminder, Wishlist


@pytest.mark.django_db
def test_send_cellar_summary_includes_wine_stats(user, wine_factory):
    current_year = date.today().year
    wine = wine_factory(
        user=user,
        name="Château Test",
        drink_to=current_year,
        price=Decimal("24.50"),
    )
    household = wine.household
    storage = user.storage_set.first()
    storage_item = StorageItem.objects.create(
        wine=wine,
        storage=storage,
        user=user,
        household=household,
    )
    DrinkRecord.objects.create(
        wine=wine,
        storage_item=storage_item,
        user=user,
        household=household,
        date_consumed=date.today(),
        rating=3,
    )
    ReorderReminder.objects.create(
        wine=wine,
        user=user,
        household=household,
        min_stock=1,
    )
    Wishlist.objects.create(
        name="Cellar Wishlist",
        user=user,
        household=household,
    )

    stdout = StringIO()
    call_command("send_cellar_summary", stdout=stdout)

    assert stdout.getvalue().strip() == "Sent 1 weekly summary email(s)"
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.subject == "Weekly Wine Cellar Summary"
    assert "Bottles in stock: 1" in message.body
    assert "Wishlist items: 1" in message.body
    assert "Upcoming drinking windows (1)" in message.body
    assert "Château Test" in message.body
    assert f"Drink by {current_year}" in message.body


@pytest.mark.django_db
def test_send_cellar_summary_skips_disabled_notifications(user):
    user_settings = get_user_settings(user)
    user_settings.notifications = False
    user_settings.save()

    stdout = StringIO()
    call_command("send_cellar_summary", stdout=stdout)

    assert stdout.getvalue().strip() == "Sent 0 weekly summary email(s)"
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_send_cellar_summary_sends_to_user_without_settings_row(django_user_model):
    """Users with no UserSettings row must still be included in the queryset.

    Guards against the ORM INNER JOIN exclusion: previously
    ``exclude(user_settings__notifications=False)`` would silently drop users
    whose UserSettings row doesn't exist yet, because Django translates the
    reverse-relation traversal into an INNER JOIN.  The new ``Q`` filter
    explicitly includes null rows so those users are still queried.
    """
    from unittest.mock import patch

    from wine_cellar.apps.user.models import UserSettings

    user = django_user_model.objects.create_user(
        username="no_settings_user",
        email="no-settings@example.com",
        password="pw",
    )
    # Verify there really is no UserSettings row for this user.
    assert not UserSettings.objects.filter(user=user).exists()

    called_for = []

    def fake_send(u, period="weekly"):
        called_for.append(u.pk)
        return False  # no household, so no email — that's fine

    with patch(
        "wine_cellar.apps.core.emails.send_cellar_summary_email",
        side_effect=fake_send,
    ):
        stdout = StringIO()
        call_command("send_cellar_summary", stdout=stdout)

    # The user with no settings row must have been included in the iteration.
    assert user.pk in called_for, (
        "send_cellar_summary_emails() excluded a user with no UserSettings row "
        "(INNER JOIN regression)"
    )
