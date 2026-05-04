import datetime
import io
import json
from decimal import Decimal
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from pytest_django.asserts import assertRedirects, assertTemplateUsed

from wine_cellar.apps.whisky.models import (
    Collection,
    FillLevel,
    Whisky,
    WhiskyDrinkRecord,
    WhiskyImage,
    WhiskyPriceHistory,
    WhiskySource,
    WhiskyStorageItem,
    WhiskyVisionExtractionLog,
    WhiskyWishlist,
)


def _test_image_upload(name="front.jpg"):
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), color="red").save(buffer, format="JPEG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


@pytest.mark.django_db
def test_homepage_unauthenticated(client):
    """Test that unauthenticated users are redirected to login."""
    r = client.get(reverse("homepage"), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("account_login") + "?next=/")
    assertTemplateUsed(response=r, template_name="account/login.html")


@pytest.mark.django_db
def test_homepage_authenticated(client, user):
    """Test that authenticated users can access the homepage."""
    client.force_login(user)
    r = client.get(reverse("homepage"), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="core/homepage.html")


@pytest.mark.django_db
def test_whisky_list_unauthenticated(client):
    """Test that unauthenticated users are redirected from whisky list."""
    r = client.get(reverse("whisky-list"), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(
        response=r,
        expected_url=reverse("account_login") + "?next=" + reverse("whisky-list"),
    )


@pytest.mark.django_db
def test_whisky_list_loads(client, user):
    """Test that whisky list page loads for authenticated users."""
    client.force_login(user)
    r = client.get(reverse("whisky-list"))
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="core/beverage_list.html")


@pytest.mark.django_db
def test_whisky_import_creates_whisky_and_stock(client, user, storage_factory):
    storage = storage_factory(
        user=user,
        household=user.user_settings.active_household,
        rows=0,
        columns=0,
        app_type="whisky",
    )
    client.force_login(user)

    csv_file = SimpleUploadedFile(
        "whiskies.csv",
        (
            "name,whisky_type,country,stock,distillery\n"
            "Imported Dram,Single Malt,Scotland,1,New Distillery\n"
        ).encode("utf-8"),
        content_type="text/csv",
    )

    preview = client.post(
        reverse("whisky-import"),
        {"action": "upload", "file": csv_file},
    )
    assert preview.status_code == HTTPStatus.OK
    assert "Step 2: Map columns" in preview.content.decode()

    response = client.post(
        reverse("whisky-import"),
        {
            "action": "import",
            "default_storage": storage.pk,
            "map_name": "name",
            "map_whisky_type": "whisky_type",
            "map_country": "country",
            "map_stock_count": "stock",
            "map_distillery": "distillery",
        },
        follow=True,
    )

    assert response.status_code == HTTPStatus.OK
    whisky = Whisky.objects.get(name="Imported Dram")
    assert whisky.distillery is not None
    assert whisky.distillery.name == "New Distillery"
    assert WhiskyStorageItem.objects.filter(whisky=whisky, deleted=False).count() == 1


@pytest.mark.django_db
def test_whisky_list_shows_user_whiskies(
    client, user, whisky_factory, whisky_storage_item_factory
):
    """Test that whisky list shows whiskies belonging to the user."""
    household = user.user_settings.active_household
    whisky = whisky_factory(user=user, name="Lagavulin 16")
    whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky=whisky,
    )
    client.force_login(user)
    r = client.get(reverse("whisky-list"))
    assert r.status_code == HTTPStatus.OK
    assert whisky in r.context["whiskies"]


@pytest.mark.django_db
def test_whisky_filter_by_collection(
    client, user, whisky_factory, whisky_storage_item_factory
):
    household = user.user_settings.active_household
    whisky_in_collection = whisky_factory(user=user)
    whisky_outside_collection = whisky_factory(user=user)
    whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky=whisky_in_collection,
    )
    whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky=whisky_outside_collection,
    )
    collection = Collection.objects.create(
        name="Investment Bottles",
        user=user,
        household=whisky_in_collection.household,
    )
    collection.whiskies.add(whisky_in_collection)

    client.force_login(user)
    r = client.get(reverse("whisky-list") + f"?collection={collection.pk}")

    assert r.status_code == HTTPStatus.OK
    assert list(r.context["whiskies"]) == [whisky_in_collection]
    assert whisky_outside_collection not in r.context["whiskies"]


@pytest.mark.django_db
def test_whisky_collection_add_and_remove(client, user, whisky_factory):
    whisky = whisky_factory(user=user)
    collection = Collection.objects.create(
        name="Dinner Party Picks",
        user=user,
        household=whisky.household,
    )

    client.force_login(user)
    add_url = reverse("whisky-collection-add", kwargs={"pk": whisky.pk})
    remove_url = reverse(
        "whisky-collection-remove",
        kwargs={"pk": whisky.pk, "collection_pk": collection.pk},
    )

    add_response = client.post(
        add_url, data={"collection_id": collection.pk}, follow=True
    )
    assert add_response.status_code == HTTPStatus.OK
    assert collection.whiskies.filter(pk=whisky.pk).exists()

    remove_response = client.post(remove_url, follow=True)
    assert remove_response.status_code == HTTPStatus.OK
    assert not collection.whiskies.filter(pk=whisky.pk).exists()


@pytest.mark.django_db
def test_whisky_collection_create_new_by_name(client, user, whisky_factory):
    whisky = whisky_factory(user=user)
    client.force_login(user)
    url = reverse("whisky-collection-add", kwargs={"pk": whisky.pk})

    response = client.post(
        url, data={"new_collection_name": "Investment Bottles"}, follow=True
    )
    assert response.status_code == HTTPStatus.OK
    assert Collection.objects.filter(
        name="Investment Bottles", household=whisky.household
    ).exists()
    collection = Collection.objects.get(
        name="Investment Bottles", household=whisky.household
    )
    assert collection.whiskies.filter(pk=whisky.pk).exists()


@pytest.mark.django_db
def test_whisky_collection_add_invalid_id(client, user, whisky_factory):
    whisky = whisky_factory(user=user)
    client.force_login(user)
    url = reverse("whisky-collection-add", kwargs={"pk": whisky.pk})

    response = client.post(url, data={"collection_id": "abc"}, follow=True)
    assert response.status_code == HTTPStatus.OK


@pytest.mark.django_db
def test_bottle_list_loads(client, user, whisky_storage_item_factory):
    """Test that whisky bottle list page loads and exposes filter context."""
    household = user.user_settings.active_household
    whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
    )
    client.force_login(user)
    r = client.get(reverse("bottle-list"))
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="whisky/bottle_list.html")
    assert "filter" in r.context


@pytest.mark.django_db
def test_bottle_list_filters_by_whisky_name(client, user, whisky_storage_item_factory):
    """Test whisky bottle list applies whisky_name filter from query params."""
    household = user.user_settings.active_household
    matching = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
        whisky__name="Lagavulin 16",
    )
    non_matching = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
        whisky__name="Ardbeg 10",
    )

    client.force_login(user)
    r = client.get(reverse("bottle-list"), {"whisky_name": "Lagavulin"})
    assert r.status_code == HTTPStatus.OK
    bottles = list(r.context["bottles"])
    assert matching in bottles
    assert non_matching not in bottles


@pytest.mark.django_db
def test_bottle_list_filters_by_multiple_fill_levels(
    client, user, whisky_storage_item_factory
):
    """Bottle list should allow multiple fill level selections."""
    household = user.user_settings.active_household
    unopened = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
        fill_level=FillLevel.UNOPENED,
    )
    opened = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
        fill_level=FillLevel.OPENED,
    )
    dreg = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
        fill_level=FillLevel.DREG,
    )

    client.force_login(user)
    r = client.get(
        reverse("bottle-list"),
        {"fill_level": [FillLevel.UNOPENED, FillLevel.OPENED]},
    )

    assert r.status_code == HTTPStatus.OK
    bottles = list(r.context["bottles"])
    assert unopened in bottles
    assert opened in bottles
    assert dreg not in bottles


@pytest.mark.django_db
def test_whisky_list_defaults_to_in_stock_and_oldest_first(
    client, user, whisky_factory, whisky_storage_item_factory
):
    household = user.user_settings.active_household
    oldest = whisky_factory(user=user, name="Oldest")
    newest = whisky_factory(user=user, name="Newest")
    out_of_stock = whisky_factory(user=user, name="Out of Stock")
    old_created = timezone.now() - datetime.timedelta(days=30)
    new_created = timezone.now() - datetime.timedelta(days=1)
    Whisky.objects.filter(pk=oldest.pk).update(created=old_created)
    Whisky.objects.filter(pk=newest.pk).update(created=new_created)

    whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky=oldest,
    )
    whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky=newest,
    )

    client.force_login(user)
    response = client.get(reverse("whisky-list"))

    assert response.status_code == HTTPStatus.OK
    assert response.context["filter"].data["has_stock"] == "1"
    assert response.context["filter"].data["order"] == "created"
    assert list(response.context["whiskies"]) == [oldest, newest]
    assert out_of_stock not in response.context["whiskies"]


@pytest.mark.django_db
def test_mark_whisky_bottle_as_given_records_recipient_and_date(
    client, user, whisky_storage_item_factory
):
    household = user.user_settings.active_household
    bottle = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
    )

    client.force_login(user)
    response = client.post(
        reverse("stock-give", kwargs={"pk": bottle.pk}),
        {
            "recipient": "Jamie",
            "given_date": "2026-04-16",
            "given_occasion": "Thank you",
        },
    )

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("whisky-detail", kwargs={"pk": bottle.whisky.pk})

    bottle.refresh_from_db()
    assert bottle.deleted is True
    assert bottle.removal_reason == WhiskyStorageItem.RemovalReason.GIVEN
    assert bottle.recipient == "Jamie"
    assert bottle.given_date == datetime.date(2026, 4, 16)
    assert bottle.given_occasion == "Thank you"
    assert bottle.finished_date is None


@pytest.mark.django_db
def test_mark_whisky_bottle_as_broken_or_lost_records_removal_reason(
    client, user, whisky_storage_item_factory
):
    household = user.user_settings.active_household
    bottle = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
    )

    client.force_login(user)
    response = client.post(reverse("stock-delete", kwargs={"pk": bottle.pk}))

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("whisky-detail", kwargs={"pk": bottle.whisky.pk})

    bottle.refresh_from_db()
    assert bottle.deleted is True
    assert bottle.removal_reason == WhiskyStorageItem.RemovalReason.REMOVED
    assert bottle.finished_date == timezone.localdate()
    assert bottle.given_date is None
    assert bottle.recipient == ""
    assert bottle.given_occasion == ""


@pytest.mark.django_db
def test_given_whisky_bottle_history_shows_recipient_and_occasion(
    client, user, whisky_storage_item_factory
):
    household = user.user_settings.active_household
    bottle = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
        deleted=True,
        removal_reason=WhiskyStorageItem.RemovalReason.GIVEN,
        recipient="Jamie",
        given_occasion="Thank you",
        given_date=datetime.date(2026, 4, 16),
    )

    client.force_login(user)
    response = client.get(reverse("bottle-history", kwargs={"pk": bottle.pk}))
    content = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert "Given away" in content
    assert "Jamie" in content
    assert "Thank you" in content


@pytest.mark.django_db
def test_whisky_bottle_history_shows_quick_log_for_active_bottle(
    client, user, whisky_storage_item_factory
):
    household = user.user_settings.active_household
    bottle = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
    )

    client.force_login(user)
    response = client.get(reverse("bottle-history", kwargs={"pk": bottle.pk}))

    assert response.status_code == HTTPStatus.OK
    assert (
        reverse("bottle-quick-log", kwargs={"pk": bottle.pk})
        in response.content.decode()
    )
    assert "Just drank this" in response.content.decode()


@pytest.mark.django_db
def test_whisky_bottle_quick_log_creates_record_and_marks_bottle_opened(
    client, user, whisky_storage_item_factory
):
    household = user.user_settings.active_household
    bottle = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
        fill_level=FillLevel.UNOPENED,
        opened_date=None,
    )

    client.force_login(user)
    response = client.post(reverse("bottle-quick-log", kwargs={"pk": bottle.pk}))

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("bottle-history", kwargs={"pk": bottle.pk})

    record = WhiskyDrinkRecord.objects.get(storage_item=bottle)
    assert record.whisky == bottle.whisky
    assert record.user == user
    assert record.household == household
    assert record.date_consumed == timezone.localdate()
    assert record.rating is None
    assert record.tasting_notes in (None, "")

    bottle.refresh_from_db()
    assert bottle.deleted is False
    assert bottle.fill_level == FillLevel.OPENED
    assert bottle.opened_date == timezone.localdate()


@pytest.mark.django_db
def test_broken_or_lost_whisky_bottle_history_shows_broken_or_lost_label(
    client, user, whisky_storage_item_factory
):
    household = user.user_settings.active_household
    bottle = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
        deleted=True,
        removal_reason=WhiskyStorageItem.RemovalReason.REMOVED,
        finished_date=datetime.date(2026, 4, 16),
    )

    client.force_login(user)
    response = client.get(reverse("bottle-history", kwargs={"pk": bottle.pk}))
    content = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert "Broken or lost" in content


@pytest.mark.django_db
def test_whisky_stock_history_orders_by_removal_date(
    client, user, whisky_factory, whisky_storage_item_factory
):
    household = user.user_settings.active_household
    older_consumed = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky=whisky_factory(user=user, name="Older Consumed"),
        deleted=True,
        finished_date=timezone.localdate() - datetime.timedelta(days=10),
    )
    newest_given = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky=whisky_factory(user=user, name="Newest Given"),
        deleted=True,
        removal_reason=WhiskyStorageItem.RemovalReason.GIVEN,
        recipient="Jamie",
        given_date=timezone.localdate() - datetime.timedelta(days=1),
    )
    middle_removed = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky=whisky_factory(user=user, name="Middle Removed"),
        deleted=True,
        removal_reason=WhiskyStorageItem.RemovalReason.REMOVED,
        finished_date=timezone.localdate() - datetime.timedelta(days=5),
    )
    undated_removed = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky=whisky_factory(user=user, name="Undated Removed"),
        deleted=True,
        removal_reason=WhiskyStorageItem.RemovalReason.REMOVED,
    )
    WhiskyStorageItem.objects.filter(pk=undated_removed.pk).update(
        created=timezone.now() - datetime.timedelta(days=20)
    )
    undated_removed.refresh_from_db()

    client.force_login(user)
    response = client.get(reverse("stock-history"))

    assert response.status_code == HTTPStatus.OK
    assert list(response.context["storage_items"])[:4] == [
        newest_given,
        middle_removed,
        older_consumed,
        undated_removed,
    ]


@pytest.mark.django_db
def test_drink_record_form_invites_bottle_status_selection(
    client, user, whisky_storage_item_factory
):
    """Test drink-record form exposes the bottle-status choice field."""
    household = user.user_settings.active_household
    bottle = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
    )

    client.force_login(user)
    response = client.get(reverse("drink-record-add", kwargs={"pk": bottle.whisky.pk}))

    assert response.status_code == HTTPStatus.OK
    assert "post_drink_status" in response.context["form"].fields


@pytest.mark.django_db
def test_drink_record_form_defaults_bottle_status_to_opened(
    client, user, whisky_storage_item_factory
):
    household = user.user_settings.active_household
    bottle = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
        fill_level=FillLevel.UNOPENED,
    )

    client.force_login(user)
    response = client.get(reverse("drink-record-add", kwargs={"pk": bottle.whisky.pk}))

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"]["post_drink_status"].value() == FillLevel.OPENED


@pytest.mark.django_db
def test_drink_record_form_exposes_fill_level_defaults_for_whisky(
    client, user, whisky_storage_item_factory
):
    household = user.user_settings.active_household
    bottle = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
        fill_level=FillLevel.DREG,
    )

    client.force_login(user)
    response = client.get(reverse("drink-record-add", kwargs={"pk": bottle.whisky.pk}))
    html = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert f'data-default-status="{FillLevel.OPENED}"' in html
    assert f'data-dreg-status="{FillLevel.DREG}"' in html
    assert f'data-fill-level="{FillLevel.DREG}"' in html


@pytest.mark.django_db
def test_drink_record_form_bound_post_disables_auto_status_updates(
    client, user, whisky_storage_item_factory
):
    from wine_cellar.apps.whisky.forms import POST_DRINK_STATUS_CONSUMED

    household = user.user_settings.active_household
    bottle = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
        fill_level=FillLevel.UNOPENED,
    )

    client.force_login(user)
    response = client.post(
        reverse("drink-record-add", kwargs={"pk": bottle.whisky.pk}),
        {
            "storage_item": bottle.pk,
            "post_drink_status": POST_DRINK_STATUS_CONSUMED,
            "date_consumed": "",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert "let isAutoManaged = false;" in response.content.decode()


@pytest.mark.django_db
def test_drink_record_with_selected_bottle_can_mark_consumed(
    client, user, whisky_storage_item_factory
):
    """Test selected bottle can be marked consumed when recording a drink."""
    from wine_cellar.apps.whisky.forms import POST_DRINK_STATUS_CONSUMED

    household = user.user_settings.active_household
    bottle = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
        fill_level=FillLevel.UNOPENED,
        deleted=False,
    )

    client.force_login(user)
    response = client.post(
        reverse("drink-record-add", kwargs={"pk": bottle.whisky.pk}),
        {
            "storage_item": bottle.pk,
            "post_drink_status": POST_DRINK_STATUS_CONSUMED,
            "date_consumed": "2024-01-15",
            "rating": 2,
        },
    )

    assert response.status_code == HTTPStatus.FOUND
    record = WhiskyDrinkRecord.objects.filter(whisky=bottle.whisky, user=user).first()
    assert record is not None
    assert record.storage_item == bottle
    bottle.refresh_from_db()
    assert bottle.deleted is True


@pytest.mark.django_db
def test_journey_timeline_view(client, user, whisky_storage_item_factory):
    household = user.user_settings.active_household
    bottle = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
        price=42,
    )
    WhiskyDrinkRecord.objects.create(
        whisky=bottle.whisky,
        user=user,
        household=household,
        date_consumed=datetime.date(2025, 1, 5),
        rating=2,
    )

    client.force_login(user)
    response = client.get(reverse("journey-timeline"))

    assert response.status_code == HTTPStatus.OK
    assert len(response.context["timeline_events"]) == 2
    assert len(response.context["monthly_consumption"]) == 1
    assert len(response.context["price_trends"]) == 1


@pytest.mark.django_db
def test_drink_record_with_selected_bottle_can_mark_opened(
    client, user, whisky_storage_item_factory
):
    """Test selected bottle can stay in stock and be marked opened."""
    household = user.user_settings.active_household
    bottle = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
        fill_level=FillLevel.UNOPENED,
        deleted=False,
    )

    client.force_login(user)
    response = client.post(
        reverse("drink-record-add", kwargs={"pk": bottle.whisky.pk}),
        {
            "storage_item": bottle.pk,
            "post_drink_status": FillLevel.OPENED,
            "date_consumed": "2024-01-15",
            "rating": 3,
        },
    )

    assert response.status_code == HTTPStatus.FOUND
    bottle.refresh_from_db()
    assert bottle.deleted is False
    assert bottle.fill_level == FillLevel.OPENED
    assert bottle.opened_date == datetime.date(2024, 1, 15)


@pytest.mark.django_db
def test_whisky_detail_loads(client, user, whisky_factory):
    """Test that whisky detail page loads for a valid whisky."""
    whisky = whisky_factory(user=user, name="Ardbeg 10")
    client.force_login(user)
    r = client.get(reverse("whisky-detail", kwargs={"pk": whisky.pk}))
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="whisky/whisky_detail.html")
    assert r.context["object"] == whisky


@pytest.mark.django_db
def test_whisky_detail_includes_price_tracking_context(client, user, whisky_factory):
    household = user.user_settings.active_household
    whisky = whisky_factory(user=user, name="Tracked Whisky", price=Decimal("50.00"))
    source = WhiskySource.objects.create(
        name="Retailer",
        user=user,
        household=household,
        url="https://example.com",
    )
    WhiskyPriceHistory.objects.create(
        whisky=whisky,
        source=source,
        price=Decimal("55.00"),
        user=user,
        household=household,
    )
    WhiskyPriceHistory.objects.create(
        whisky=whisky,
        price=Decimal("60.00"),
        user=user,
        household=household,
    )
    client.force_login(user)

    response = client.get(reverse("whisky-detail", kwargs={"pk": whisky.pk}))

    assert response.status_code == HTTPStatus.OK
    assert response.context["price_history_latest"].price == Decimal("60.00")
    assert len(response.context["price_history_entries"]) == 2
    assert (
        response.context["price_history_form"]
        .fields["source"]
        .queryset.filter(pk=source.pk)
        .exists()
    )


@pytest.mark.django_db
def test_can_add_whisky_price_history(client, user, whisky_factory):
    household = user.user_settings.active_household
    whisky = whisky_factory(user=user, name="Tracked Whisky")
    source = WhiskySource.objects.create(
        name="Retailer",
        user=user,
        household=household,
        url="https://example.com",
    )
    client.force_login(user)

    response = client.post(
        reverse("whisky-price-history-add", kwargs={"pk": whisky.pk}),
        {"price": "62.50", "source": source.pk},
    )

    assert response.status_code == HTTPStatus.FOUND
    assert (
        response.url
        == reverse("whisky-detail", kwargs={"pk": whisky.pk}) + "#price-tracking"
    )
    history_entry = WhiskyPriceHistory.objects.get(whisky=whisky)
    assert history_entry.price == Decimal("62.50")
    assert history_entry.source == source
    assert history_entry.user == user
    assert history_entry.household == household


@pytest.mark.django_db
def test_whisky_detail_shows_carousel_controls_for_multiple_images(
    client, user, whisky_factory, clear_image_folder
):
    whisky = whisky_factory(user=user)
    WhiskyImage.objects.create(
        whisky=whisky,
        user=user,
        image=_test_image_upload("front.jpg"),
        image_type=WhiskyImage.ImageType.LABEL_FRONT,
    )
    WhiskyImage.objects.create(
        whisky=whisky,
        user=user,
        image=_test_image_upload("back.jpg"),
        image_type=WhiskyImage.ImageType.LABEL_BACK,
    )
    client.force_login(user)

    response = client.get(reverse("whisky-detail", kwargs={"pk": whisky.pk}))

    assert response.status_code == HTTPStatus.OK
    content = response.content.decode()
    assert 'class="image-controls"' in content
    assert 'class="wine-prev"' in content
    assert 'class="wine-next"' in content


@pytest.mark.django_db
def test_whisky_detail_record_drink_link_preserves_selected_storage_item(
    client, user, whisky_storage_item_factory
):
    household = user.user_settings.active_household
    bottle = whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
    )
    client.force_login(user)

    response = client.get(
        reverse("whisky-detail", kwargs={"pk": bottle.whisky.pk}),
        {"storage_item": bottle.pk},
    )

    assert response.status_code == HTTPStatus.OK
    expected_drink_url = (
        reverse("drink-record-add", kwargs={"pk": bottle.whisky.pk})
        + f"?storage_item={bottle.pk}"
    )
    assert f'href="{expected_drink_url}"' in response.content.decode()


@pytest.mark.django_db
def test_whisky_detail_uses_latest_successful_extraction_log(
    client, user, whisky_factory
):
    whisky = whisky_factory(user=user, name="Ardbeg 10")
    household = whisky.household
    WhiskyVisionExtractionLog.objects.create(
        user=user,
        household=household,
        whisky=whisky,
        extracted_data={"name": whisky.name},
        confidence="medium",
        extracted_fields=["name"],
        was_successful=True,
    )
    latest_success = WhiskyVisionExtractionLog.objects.create(
        user=user,
        household=household,
        whisky=whisky,
        extracted_data={"name": whisky.name},
        confidence="high",
        extracted_fields=["name"],
        was_successful=True,
    )
    WhiskyVisionExtractionLog.objects.create(
        user=user,
        household=household,
        whisky=whisky,
        extracted_data={"name": whisky.name},
        confidence="low",
        extracted_fields=["name"],
        was_successful=False,
    )

    client.force_login(user)
    r = client.get(reverse("whisky-detail", kwargs={"pk": whisky.pk}))

    assert r.status_code == HTTPStatus.OK
    assert r.context["extraction_log"].pk == latest_success.pk


@pytest.mark.django_db
def test_whisky_detail_unauthenticated(client, whisky_factory, user):
    """Test that unauthenticated users are redirected from whisky detail."""
    whisky = whisky_factory(user=user)
    r = client.get(reverse("whisky-detail", kwargs={"pk": whisky.pk}), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="account/login.html")


@pytest.mark.django_db
def test_whisky_create_get(client, user):
    """Test that the whisky create form loads."""
    client.force_login(user)
    r = client.get(reverse("whisky-add"))
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="whisky/whisky_create.html")
    assertTemplateUsed(response=r, template_name="core/beverage_create.html")
    assert "form" in r.context


@pytest.mark.django_db
def test_whisky_create_marks_cask_type_as_creatable_for_vision_autofill(client, user):
    """Whisky vision autofill should mark cask type as a creatable select."""
    client.force_login(user)

    response = client.get(reverse("whisky-add"))

    assert response.status_code == HTTPStatus.OK
    assert "cask_type" in response.context["vision_extraction_config"]["createFields"]


@pytest.mark.django_db
def test_whisky_create_prefills_distillery_when_scan_returns_full_whisky_name(
    client, user, distillery_factory
):
    """Scan prefill should still resolve an existing distillery from the whisky name."""
    distillery = distillery_factory(name="Lagavulin")
    client.force_login(user)

    session = client.session
    session["extraction_result"] = {
        "confidence": "medium",
        "extracted_fields": ["name", "distillery"],
        "errors": [],
        "scanned_image": "dGVzdA==",
        "extracted_data": {
            "name": "Lagavulin 16",
            "distillery": "Lagavulin 16",
        },
    }
    session.save()

    response = client.get(reverse("whisky-add"))

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].initial["distillery"] == distillery.pk


@pytest.mark.django_db
def test_whisky_extract_vision_infers_distillery_from_whisky_name(
    client, user, distillery_factory
):
    """AJAX auto-fill should infer a known distillery from the whisky name."""
    distillery = distillery_factory(name="Lagavulin")
    client.force_login(user)
    image = SimpleUploadedFile(
        "label.jpg", b"fake-image-bytes", content_type="image/jpeg"
    )

    with (
        patch(
            "wine_cellar.apps.whisky.services.barcode_service.WhiskyBarcodeScanner"
        ) as mock_scanner_cls,
        patch(
            "wine_cellar.apps.whisky.services.vision_extraction.WhiskyVisionExtractor"
        ) as mock_vision_cls,
    ):
        mock_scanner = MagicMock()
        mock_scanner.scan_and_match.return_value = {
            "matched": False,
            "barcode": None,
            "whisky_data": None,
            "all_barcodes": [],
        }
        mock_scanner_cls.return_value = mock_scanner

        mock_vision = MagicMock()
        mock_vision.extract_from_images.return_value = {
            "data": {"name": "Lagavulin 16"},
            "confidence": "medium",
            "extracted_fields": ["name"],
            "errors": [],
            "field_confidence": {"name": "high"},
        }
        mock_vision_cls.return_value = mock_vision

        response = client.post(
            reverse("whisky-extract-vision"),
            {"image_front_label": image},
        )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["success"] is True
    assert data["match_type"] == "vision"
    assert data["data"]["distillery"] == distillery.pk
    assert "distillery_name" not in data["data"]


@pytest.mark.django_db
def test_whisky_extract_vision_trims_unresolved_fk_names(client, user):
    """AJAX auto-fill trims unresolved FK names and drops blank values."""
    client.force_login(user)
    image = SimpleUploadedFile(
        "label.jpg", b"fake-image-bytes", content_type="image/jpeg"
    )

    with (
        patch(
            "wine_cellar.apps.whisky.services.barcode_service.WhiskyBarcodeScanner"
        ) as mock_scanner_cls,
        patch(
            "wine_cellar.apps.whisky.services.vision_extraction.WhiskyVisionExtractor"
        ) as mock_vision_cls,
    ):
        mock_scanner = MagicMock()
        mock_scanner.scan_and_match.return_value = {
            "matched": False,
            "barcode": None,
            "whisky_data": None,
            "all_barcodes": [],
        }
        mock_scanner_cls.return_value = mock_scanner

        mock_vision = MagicMock()
        mock_vision.extract_from_images.return_value = {
            "data": {
                "name": "Mystery Dram",
                "distillery": "  Unknown Distillery  ",
                "region": "   ",
                "bottler": "  Indie Bottler  ",
            },
            "confidence": "medium",
            "extracted_fields": ["name", "distillery", "region", "bottler"],
            "errors": [],
            "field_confidence": {"name": "high"},
        }
        mock_vision_cls.return_value = mock_vision

        response = client.post(
            reverse("whisky-extract-vision"),
            {"image_front_label": image},
        )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["success"] is True
    assert data["data"]["distillery_name"] == "Unknown Distillery"
    assert data["data"]["bottler_name"] == "Indie Bottler"
    assert "region_name" not in data["data"]


@pytest.mark.django_db
def test_whisky_create_unauthenticated(client):
    """Test that unauthenticated users are redirected from whisky create."""
    r = client.get(reverse("whisky-add"), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(
        response=r,
        expected_url=reverse("account_login") + "?next=" + reverse("whisky-add"),
    )


@pytest.mark.django_db
def test_whisky_create_post_valid(client, user):
    """Test creating a whisky via POST with valid data."""
    client.force_login(user)
    data = {
        "name": "Lagavulin 16",
        "whisky_type": "SM",
        "abv": 43.0,
        "size": "0.70",
        "country": "GB",
        "comment": "",
        "price": "",
        "rating": "",
    }
    assert not Whisky.objects.filter(user=user).exists()
    r = client.post(reverse("whisky-add"), data, follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("whisky-list"))
    assert Whisky.objects.filter(user=user).exists()
    whisky = Whisky.objects.get(user=user, name="Lagavulin 16")
    assert whisky.whisky_type == "SM"
    assert whisky.abv == 43.0


@pytest.mark.django_db
def test_whisky_create_saves_front_label_image(client, user, clear_image_folder):
    client.force_login(user)
    response = client.post(
        reverse("whisky-add"),
        {
            "name": "Lagavulin 16",
            "whisky_type": "SM",
            "abv": 43.0,
            "size": "0.70",
            "country": "GB",
            "comment": "",
            "price": "",
            "rating": "",
            "image_front_label": _test_image_upload(),
        },
        follow=True,
    )

    assert response.status_code == HTTPStatus.OK
    whisky = Whisky.objects.get(user=user, name="Lagavulin 16")
    assert (
        WhiskyImage.objects.filter(
            whisky=whisky,
            image_type=WhiskyImage.ImageType.LABEL_FRONT,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_whisky_create_post_empty(client, user):
    """Test that submitting an empty form shows validation errors."""
    client.force_login(user)
    r = client.post(reverse("whisky-add"), {})
    assert r.status_code == HTTPStatus.OK
    form = r.context["form"]
    assert not form.is_valid()
    assertTemplateUsed(response=r, template_name="whisky/whisky_create.html")


@pytest.mark.django_db
def test_whisky_delete(client, user, whisky_factory):
    """Test deleting a whisky."""
    whisky = whisky_factory(user=user, name="DeleteMe")
    whisky_pk = whisky.pk
    client.force_login(user)

    # GET shows confirmation page
    r = client.get(reverse("whisky-delete", kwargs={"pk": whisky_pk}))
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="core/confirm_delete.html")

    # POST soft-deletes the whisky
    r = client.post(reverse("whisky-delete", kwargs={"pk": whisky_pk}), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("whisky-list"))
    # Soft delete: record still exists in DB but is marked deleted
    assert Whisky.objects.filter(pk=whisky_pk, deleted=True).exists()
    assert not Whisky.objects.filter(pk=whisky_pk, deleted=False).exists()


@pytest.mark.django_db
def test_whisky_delete_unauthenticated(client, user, whisky_factory):
    """Test that unauthenticated users cannot delete a whisky."""
    whisky = whisky_factory(user=user)
    r = client.post(reverse("whisky-delete", kwargs={"pk": whisky.pk}), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="account/login.html")
    # Whisky should still exist
    assert Whisky.objects.filter(pk=whisky.pk).exists()


@pytest.mark.django_db
def test_whisky_detail_404_for_other_user(client, user, whisky_factory):
    """Test that users cannot access whiskies belonging to other users."""
    from wine_cellar.apps.user.tests.factories import UserFactory

    other_user = UserFactory()
    whisky = whisky_factory(user=other_user)
    client.force_login(user)
    r = client.get(reverse("whisky-detail", kwargs={"pk": whisky.pk}))
    assert r.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.django_db
def test_whisky_create_post_with_distillery(client, user, distillery_factory):
    """Test creating a whisky with a distillery reference."""
    distillery = distillery_factory(name="Laphroaig")
    client.force_login(user)
    data = {
        "name": "Laphroaig 10",
        "whisky_type": "SM",
        "abv": 40.0,
        "size": "0.70",
        "country": "GB",
        "distillery": distillery.pk,
        "age_statement": 10,
        "comment": "",
        "price": "",
        "rating": "",
    }
    r = client.post(reverse("whisky-add"), data, follow=True)
    assert r.status_code == HTTPStatus.OK
    whisky = Whisky.objects.get(user=user, name="Laphroaig 10")
    assert whisky.distillery == distillery
    assert whisky.age_statement == 10


@pytest.mark.django_db
def test_whisky_create_from_wishlist_prefills_and_marks_purchased(
    client, user, distillery_factory, whisky_region_factory
):
    distillery = distillery_factory(name="Talisker")
    region = whisky_region_factory(name="Islands")
    household = user.user_settings.active_household
    wishlist_item = WhiskyWishlist.objects.create(
        name="Talisker 10",
        user=user,
        household=household,
        whisky_type="SM",
        distillery=distillery,
        region=region,
        age_statement=10,
        external_url="https://example.com/whisky/talisker-10",
        notes="Birthday dram",
    )
    client.force_login(user)

    response = client.get(reverse("whisky-add") + f"?wishlist_item={wishlist_item.pk}")

    assert response.status_code == HTTPStatus.OK
    form = response.context["form"]
    assert form.initial["name"] == "Talisker 10"
    assert form.initial["distillery"] == distillery.pk
    assert form.initial["region"] == region.pk
    assert form.initial["comment"] == "Birthday dram"

    post_response = client.post(
        reverse("whisky-add"),
        {
            "name": "Talisker 10",
            "whisky_type": "SM",
            "abv": 45.8,
            "size": "0.70",
            "country": "GB",
            "wishlist_item": wishlist_item.pk,
        },
        follow=True,
    )

    assert post_response.status_code == HTTPStatus.OK
    wishlist_item.refresh_from_db()
    assert wishlist_item.purchased is True


@pytest.mark.django_db
def test_whisky_stock_add_uses_shared_template(client, user, whisky_factory):
    whisky = whisky_factory(user=user)
    client.force_login(user)

    response = client.get(reverse("stock-add", kwargs={"pk": whisky.pk}))

    assert response.status_code == HTTPStatus.OK
    assertTemplateUsed(response, "whisky/stock_add.html")
    assertTemplateUsed(response, "core/stock_add.html")
    assert response.context["whisky"].pk == whisky.pk


@pytest.mark.django_db
def test_whisky_update_replaces_front_image_and_clears_back_image(
    client, user, whisky_factory, clear_image_folder
):
    whisky = whisky_factory(user=user)
    front_image = WhiskyImage.objects.create(
        whisky=whisky,
        user=user,
        image=_test_image_upload("front-existing.jpg"),
        image_type=WhiskyImage.ImageType.LABEL_FRONT,
    )
    WhiskyImage.objects.create(
        whisky=whisky,
        user=user,
        image=_test_image_upload("back-existing.jpg"),
        image_type=WhiskyImage.ImageType.LABEL_BACK,
    )

    client.force_login(user)
    response = client.post(
        reverse("whisky-edit", kwargs={"pk": whisky.pk}),
        {
            "name": whisky.name,
            "whisky_type": whisky.whisky_type,
            "abv": whisky.abv,
            "size": whisky.size,
            "country": whisky.country,
            "comment": whisky.comment,
            "price": whisky.price or "",
            "rating": whisky.rating or "",
            "image_front_label": _test_image_upload("front-replacement.jpg"),
            "image_back_label-clear": "on",
        },
        follow=True,
    )

    assert response.status_code == HTTPStatus.OK
    front_images = WhiskyImage.objects.filter(
        whisky=whisky,
        image_type=WhiskyImage.ImageType.LABEL_FRONT,
    )
    assert front_images.count() == 1
    assert front_images.get().pk != front_image.pk
    assert not WhiskyImage.objects.filter(
        whisky=whisky,
        image_type=WhiskyImage.ImageType.LABEL_BACK,
    ).exists()


@pytest.mark.django_db
def test_whisky_bottle_edit_next_list_redirects_to_bottle_list(
    client, user, whisky_storage_item_factory
):
    storage_item = whisky_storage_item_factory(
        user=user,
        household=user.user_settings.active_household,
        storage__user=user,
        storage__household=user.user_settings.active_household,
        whisky__user=user,
        whisky__household=user.user_settings.active_household,
        row=1,
        column=1,
    )
    client.force_login(user)

    response = client.post(
        reverse("bottle-edit", kwargs={"pk": storage_item.pk}) + "?next=list",
        {
            "storage": storage_item.storage.pk,
            "row": 1,
            "column": 1,
            "price": "",
            "rating": "",
            "fill_level": storage_item.fill_level,
            "owner": storage_item.owner,
        },
        follow=True,
    )

    assert response.status_code == HTTPStatus.OK
    assert response.redirect_chain[-1][0].endswith(reverse("bottle-list"))


# ---------------------------------------------------------------------------
# storage_grid_data – whisky mode
# ---------------------------------------------------------------------------


def _make_storage_item(whisky_storage_item_factory, user, cask_type):
    """Helper: create a storage item for a whisky with the given cask_type."""
    household = user.user_settings.active_household
    return whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
        whisky__cask_type=cask_type,
        row=1,
        column=1,
    )


@pytest.mark.django_db
def test_storage_grid_data_unauthenticated(client):
    """Unauthenticated request to storage-grid-data redirects to login."""
    r = client.get(reverse("storage-grid-data"))
    assert r.status_code == HTTPStatus.FOUND
    assert reverse("account_login") in r["Location"]


@pytest.mark.django_db
def test_storage_grid_data_bourbon_cask_type(client, user, whisky_storage_item_factory):
    """A whisky with a bourbon cask_type returns wine_type_class='cask-bourbon'."""
    item = _make_storage_item(whisky_storage_item_factory, user, "Bourbon")
    client.force_login(user)
    r = client.get(
        reverse("storage-grid-data"),
        {"storage_id": item.storage.pk},
    )
    assert r.status_code == HTTPStatus.OK
    data = json.loads(r.content)
    wines = [
        w["wine"]
        for s in data["storages"]
        for w in s["items"]
        if w["wine"]["id"] == item.whisky.pk
    ]
    assert wines, "Expected at least one matching item in grid data"
    assert wines[0]["wine_type_class"] == "cask-bourbon"


@pytest.mark.django_db
def test_storage_grid_data_sherry_cask_type(client, user, whisky_storage_item_factory):
    """A whisky with a sherry cask_type returns wine_type_class='cask-sherry'."""
    item = _make_storage_item(whisky_storage_item_factory, user, "Sherry (Oloroso)")
    client.force_login(user)
    r = client.get(
        reverse("storage-grid-data"),
        {"storage_id": item.storage.pk},
    )
    assert r.status_code == HTTPStatus.OK
    data = json.loads(r.content)
    wines = [
        w["wine"]
        for s in data["storages"]
        for w in s["items"]
        if w["wine"]["id"] == item.whisky.pk
    ]
    assert wines, "Expected at least one matching item in grid data"
    assert wines[0]["wine_type_class"] == "cask-sherry"


@pytest.mark.django_db
def test_storage_grid_data_other_cask_type(client, user, whisky_storage_item_factory):
    """A whisky with an unrecognised cask_type returns wine_type_class='cask-other'."""
    item = _make_storage_item(whisky_storage_item_factory, user, "Rum")
    client.force_login(user)
    r = client.get(
        reverse("storage-grid-data"),
        {"storage_id": item.storage.pk},
    )
    assert r.status_code == HTTPStatus.OK
    data = json.loads(r.content)
    wines = [
        w["wine"]
        for s in data["storages"]
        for w in s["items"]
        if w["wine"]["id"] == item.whisky.pk
    ]
    assert wines, "Expected at least one matching item in grid data"
    assert wines[0]["wine_type_class"] == "cask-other"


@pytest.mark.django_db
def test_storage_grid_data_empty_cask_type(client, user, whisky_storage_item_factory):
    """A whisky with an empty cask_type returns wine_type_class='cask-other'."""
    item = _make_storage_item(whisky_storage_item_factory, user, "")
    client.force_login(user)
    r = client.get(
        reverse("storage-grid-data"),
        {"storage_id": item.storage.pk},
    )
    assert r.status_code == HTTPStatus.OK
    data = json.loads(r.content)
    wines = [
        w["wine"]
        for s in data["storages"]
        for w in s["items"]
        if w["wine"]["id"] == item.whisky.pk
    ]
    assert wines, "Expected at least one matching item in grid data"
    assert wines[0]["wine_type_class"] == "cask-other"


@pytest.mark.django_db
def test_storage_grid_data_mixed_finish_prioritises_sherry(
    client, user, whisky_storage_item_factory
):
    """A multi-cask string containing sherry returns wine_type_class='cask-sherry'."""
    item = _make_storage_item(
        whisky_storage_item_factory, user, "Bourbon, Sherry (Oloroso)"
    )
    client.force_login(user)
    r = client.get(
        reverse("storage-grid-data"),
        {"storage_id": item.storage.pk},
    )
    assert r.status_code == HTTPStatus.OK
    data = json.loads(r.content)
    wines = [
        w["wine"]
        for s in data["storages"]
        for w in s["items"]
        if w["wine"]["id"] == item.whisky.pk
    ]
    assert wines, "Expected at least one matching item in grid data"
    assert wines[0]["wine_type_class"] == "cask-sherry"


@pytest.mark.django_db
def test_storage_grid_data_includes_utilization_stats(
    client, user, whisky_storage_item_factory
):
    item = _make_storage_item(whisky_storage_item_factory, user, "Bourbon")
    storage = item.storage
    storage.rows = 2
    storage.columns = 2
    storage.cell_mask = [[1, 1], [1, 2], [2, 1]]
    storage.save(update_fields=["rows", "columns", "cell_mask"])
    whisky_storage_item_factory(
        user=user,
        household=user.user_settings.active_household,
        storage=storage,
        whisky__user=user,
        whisky__household=user.user_settings.active_household,
        row=1,
        column=2,
    )
    client.force_login(user)
    r = client.get(reverse("storage-grid-data"), {"storage_id": storage.pk})
    assert r.status_code == HTTPStatus.OK
    data = json.loads(r.content)
    storage_data = next(s for s in data["storages"] if s["id"] == storage.pk)
    assert storage_data["used_slots"] == 2
    assert storage_data["total_slots"] == 3
    assert storage_data["utilization_percent"] == 67


@pytest.mark.django_db
def test_cellar_value_uses_whisky_price_as_fallback(
    client, user, whisky_factory, whisky_storage_item_factory
):
    """Cellar value total uses whisky.price when storage_item.price is NULL."""
    Whisky.objects.filter(user=user).delete()
    storage = user.storage_set.first()
    whisky = whisky_factory(user=user, price=50.00)
    # item has no price; should fall back to whisky.price=50
    whisky_storage_item_factory(whisky=whisky, storage=storage, price=None)
    client.force_login(user)
    r = client.get(reverse("cellar-value"))
    assert r.status_code == HTTPStatus.OK
    assert r.context_data["total_value"] == 50


@pytest.mark.django_db
def test_cellar_value_zero_item_price_not_overridden(
    client, user, whisky_factory, whisky_storage_item_factory
):
    """An explicit item price of zero is respected and not replaced by whisky.price."""
    Whisky.objects.filter(user=user).delete()
    storage = user.storage_set.first()
    whisky = whisky_factory(user=user, price=50.00)
    # item price explicitly set to 0 — must NOT fall through to whisky.price
    whisky_storage_item_factory(whisky=whisky, storage=storage, price=0)
    client.force_login(user)
    r = client.get(reverse("cellar-value"))
    assert r.status_code == HTTPStatus.OK
    assert r.context_data["total_value"] == 0


@pytest.mark.django_db
def test_cellar_value_by_distillery_uses_whisky_price_fallback(
    client, user, whisky_factory, distillery_factory, whisky_storage_item_factory
):
    """Per-distillery breakdown uses whisky.price when storage_item.price is NULL."""
    Whisky.objects.filter(user=user).delete()
    storage = user.storage_set.first()
    distillery = distillery_factory()
    whisky = whisky_factory(user=user, distillery=distillery, price=75.00)
    whisky_storage_item_factory(whisky=whisky, storage=storage, price=None)
    client.force_login(user)
    r = client.get(reverse("cellar-value"))
    assert r.status_code == HTTPStatus.OK
    by_group = r.context_data["by_group"]
    assert by_group[distillery.name]["value"] == 75


@pytest.mark.django_db
def test_whisky_stats_dashboard_renders(client, user):
    """Stats dashboard page loads successfully for authenticated whisky users."""
    client.force_login(user)
    r = client.get(reverse("stats-dashboard"))
    assert r.status_code == HTTPStatus.OK


@pytest.mark.django_db
def test_whisky_stats_dashboard_unauthenticated(client):
    """Unauthenticated users are redirected from the stats dashboard."""
    r = client.get(reverse("stats-dashboard"))
    assert r.status_code == HTTPStatus.FOUND


@pytest.mark.django_db
def test_whisky_stats_dashboard_by_type(
    client, user, whisky_factory, whisky_storage_item_factory
):
    """Stats dashboard shows correct by-type breakdown for whiskies."""

    Whisky.objects.filter(user=user).delete()
    storage = user.storage_set.first()
    w = whisky_factory(user=user, whisky_type="SM")  # Single Malt, in stock
    whisky_storage_item_factory(whisky=w, storage=storage)
    client.force_login(user)
    r = client.get(reverse("stats-dashboard"))
    assert r.status_code == HTTPStatus.OK
    by_type = r.context_data["by_type"]
    assert by_type.get("Single Malt", 0) == 1


@pytest.mark.django_db
def test_whisky_stats_dashboard_spending_trends(
    client, user, whisky_factory, whisky_storage_item_factory
):
    """Stats dashboard groups whisky spending by month and year."""
    storage = user.storage_set.first()
    whisky = whisky_factory(user=user, price=Decimal("45.00"))
    january_item = whisky_storage_item_factory(
        whisky=whisky,
        storage=storage,
        price=Decimal("40.00"),
    )
    march_item = whisky_storage_item_factory(
        whisky=whisky,
        storage=storage,
        price=None,
    )
    january_created = timezone.make_aware(datetime.datetime(2024, 1, 8, 12, 0))
    march_created = timezone.make_aware(datetime.datetime(2024, 3, 14, 12, 0))
    WhiskyStorageItem.objects.filter(pk=january_item.pk).update(created=january_created)
    WhiskyStorageItem.objects.filter(pk=march_item.pk).update(created=march_created)

    client.force_login(user)
    r = client.get(reverse("stats-dashboard"))

    assert r.status_code == HTTPStatus.OK
    assert r.context_data["spend_by_month"] == [
        {"month": january_created.date().replace(day=1), "amount": Decimal("40.00")},
        {"month": march_created.date().replace(day=1), "amount": Decimal("45.00")},
    ]
    assert r.context_data["spend_by_year"] == [
        {"year": 2024, "amount": Decimal("85.00")}
    ]
    assert "Monthly Spend" in r.content.decode()
    assert "Yearly Spend" in r.content.decode()


@pytest.mark.django_db
def test_whisky_stats_dashboard_rating_distribution(
    client, user, whisky_factory, whisky_storage_item_factory
):
    """Stats dashboard shows rating distribution of whiskies in cellar."""
    storage = user.storage_set.first()
    whisky_3_stars = whisky_factory(user=user, rating=3)
    whisky_2_stars = whisky_factory(user=user, rating=2)
    whisky_1_star = whisky_factory(user=user, rating=1)
    whisky_unrated = whisky_factory(user=user, rating=None)

    whisky_storage_item_factory(whisky=whisky_3_stars, storage=storage)
    whisky_storage_item_factory(whisky=whisky_2_stars, storage=storage)
    whisky_storage_item_factory(whisky=whisky_1_star, storage=storage)
    whisky_storage_item_factory(whisky=whisky_unrated, storage=storage)

    client.force_login(user)
    r = client.get(reverse("stats-dashboard"))

    assert r.status_code == HTTPStatus.OK
    by_rating = r.context_data["by_rating"]

    assert by_rating == {0: 0, 1: 1, 2: 1, 3: 1}
    assert "Rating Distribution" in r.content.decode()


@pytest.mark.django_db
def test_whisky_check_duplicate_unauthenticated(client):
    """Unauthenticated requests to the check-duplicate endpoint are redirected."""
    r = client.get(reverse("whisky-check-duplicate"), {"name": "Lagavulin 16"})
    assert r.status_code == HTTPStatus.FOUND


@pytest.mark.django_db
def test_whisky_check_duplicate_no_matches(client, user):
    """Returns empty list when no similar whiskies exist."""
    client.force_login(user)
    r = client.get(reverse("whisky-check-duplicate"), {"name": "Unique Distillery"})
    assert r.status_code == HTTPStatus.OK
    data = r.json()
    assert data["similar"] == []


@pytest.mark.django_db
def test_whisky_check_duplicate_short_name(client, user):
    """Returns empty list when name is too short to check."""
    client.force_login(user)
    r = client.get(reverse("whisky-check-duplicate"), {"name": "La"})
    assert r.status_code == HTTPStatus.OK
    assert r.json()["similar"] == []


@pytest.mark.django_db
def test_whisky_check_duplicate_finds_similar(client, user, whisky_factory):
    """Returns existing whisky when name closely matches."""
    whisky_factory(user=user, name="Lagavulin 16")
    client.force_login(user)
    r = client.get(reverse("whisky-check-duplicate"), {"name": "Lagavulin 16"})
    assert r.status_code == HTTPStatus.OK
    data = r.json()
    assert len(data["similar"]) >= 1
    names = [item["name"] for item in data["similar"]]
    assert "Lagavulin 16" in names


@pytest.mark.django_db
def test_whisky_check_duplicate_returns_url(client, user, whisky_factory):
    """Each similar entry contains a URL linking to the whisky detail page."""
    whisky = whisky_factory(user=user, name="Glenfarclas 15")
    client.force_login(user)
    r = client.get(reverse("whisky-check-duplicate"), {"name": "Glenfarclas 15"})
    assert r.status_code == HTTPStatus.OK
    data = r.json()
    assert len(data["similar"]) >= 1
    assert f"/whisky/{whisky.pk}/" in data["similar"][0]["url"]


@pytest.mark.django_db
def test_whisky_check_duplicate_no_cross_household(
    client, user, whisky_factory, user_factory
):
    """Does not return whiskies belonging to a different user's household."""
    other_user = user_factory()
    whisky_factory(user=other_user, name="Ardbeg Uigeadail")
    client.force_login(user)
    r = client.get(reverse("whisky-check-duplicate"), {"name": "Ardbeg Uigeadail"})
    assert r.status_code == HTTPStatus.OK
    assert r.json()["similar"] == []


# ---------------------------------------------------------------------------
# Whisky drink record tasting wheel tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_whisky_drink_record_create_with_taste_descriptors(
    client, user, whisky_factory
):
    """Test that taste descriptors can be saved on whisky drink record creation."""
    import json
    from datetime import date

    whisky = whisky_factory(user=user)
    client.force_login(user)
    descriptors = ["Smoky", "Peat", "Citrus"]
    r = client.post(
        reverse("drink-record-add", kwargs={"pk": whisky.pk}),
        {
            "date_consumed": date.today().isoformat(),
            "tasting_notes": "Excellent dram",
            "rating": "3",
            "taste_descriptors": json.dumps(descriptors),
        },
    )
    assert r.status_code == HTTPStatus.FOUND

    from wine_cellar.apps.whisky.models import WhiskyDrinkRecord

    record = WhiskyDrinkRecord.objects.filter(whisky=whisky).first()
    assert record is not None
    assert record.taste_descriptors == descriptors


@pytest.mark.django_db
def test_whisky_drink_record_edit_with_taste_descriptors(
    client, user, whisky_factory
):
    """Test that taste descriptors can be updated on whisky drink record edit."""
    import json
    from datetime import date

    from wine_cellar.apps.whisky.models import WhiskyDrinkRecord

    whisky = whisky_factory(user=user)
    household = user.user_settings.active_household
    record = WhiskyDrinkRecord.objects.create(
        whisky=whisky,
        user=user,
        household=household,
        date_consumed=date.today(),
        taste_descriptors=["Smoky"],
    )
    client.force_login(user)
    new_descriptors = ["Spice", "Oak"]
    r = client.post(
        reverse("drink-record-edit", kwargs={"pk": record.pk}),
        {
            "date_consumed": date.today().isoformat(),
            "tasting_notes": "Updated notes",
            "rating": "2",
            "taste_descriptors": json.dumps(new_descriptors),
        },
    )
    assert r.status_code == HTTPStatus.FOUND
    record.refresh_from_db()
    assert record.taste_descriptors == new_descriptors
