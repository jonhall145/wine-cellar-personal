from datetime import date
from http import HTTPStatus

import pytest
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import (
    assertRedirects,
    assertTemplateUsed,
)

from wine_cellar.apps.storage.models import BottleMoveHistory, Storage, StorageItem


@pytest.mark.django_db
def test_storage_create_page_unauthenticated(client, user):
    r = client.get(reverse("storage-add"), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(
        response=r,
        expected_url=reverse("account_login") + "?next=" + reverse("storage-add"),
    )
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="account/login.html")


@pytest.mark.django_db
def test_storage_create_page(client, user):
    client.force_login(user)
    r = client.get(reverse("storage-add"), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="storage_create.html")


@pytest.mark.django_db
def test_storage_create_post_empty(client, user):
    client.force_login(user)
    data = {}
    r = client.post(reverse("storage-add"), data)
    assert r.status_code == HTTPStatus.OK
    f = r.context["form"]
    assert not f.is_valid()
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="storage_create.html")
    assert Storage.objects.count() == 1


@pytest.mark.django_db
def test_storage_create_post_unauthenticated(client, user):
    r = client.post(reverse("storage-add"), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(
        response=r,
        expected_url=reverse("account_login") + "?next=" + reverse("storage-add"),
    )
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="account/login.html")
    assert Storage.objects.count() == 1


@pytest.mark.django_db
def test_storage_create_post(client, user):
    client.force_login(user)
    data = {
        "name": "Shelf 1",
        "location": "Basement",
        "rows": 5,
        "columns": 10,
    }

    assert Storage.objects.count() == 1
    r = client.post(reverse("storage-add"), data=data, follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("storage-list"))
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="storage_list.html")
    assert Storage.objects.count() == 2
    storage = Storage.objects.last()
    assert storage.user == user
    assert storage.name == data["name"]
    assert storage.location == data["location"]
    assert storage.rows == data["rows"]
    assert storage.columns == data["columns"]


@pytest.mark.django_db
def test_storage_create_post_invalid(client, user):
    client.force_login(user)
    data = {
        "name": "Merlot",
        "rows": 5,
        "columns": 10,
    }
    assert Storage.objects.count() == 1
    r = client.get(reverse("storage-add"))
    r = client.post(reverse("storage-add"), data=data, follow=True)
    assert r.status_code == HTTPStatus.OK
    assert r.context_data["form"].errors


@pytest.mark.django_db
def test_storage_update_post(client, user):
    client.force_login(user)
    storage = Storage.objects.first()
    data = {
        "name": storage.name,
        "location": "Basement",
        "rows": 1,
        "columns": 10,
    }
    assert Storage.objects.count() == 1
    r = client.post(
        reverse("storage-edit", kwargs={"pk": storage.pk}), data=data, follow=True
    )
    assert r.status_code == HTTPStatus.OK
    assertRedirects(
        response=r, expected_url=reverse("storage-detail", kwargs={"pk": storage.pk})
    )
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="storage_detail.html")
    storage.refresh_from_db()
    assert storage.user == user
    assert storage.rows == data["rows"]
    assert storage.columns == data["columns"]


@pytest.mark.django_db
def test_storage_cant_delete_only(client, user):
    client.force_login(user)
    assert Storage.objects.count() == 1
    storage = Storage.objects.first()
    r = client.post(reverse("storage-delete", kwargs={"pk": storage.pk}), follow=True)
    assert r.status_code == HTTPStatus.OK
    assert r.context_data["form"].errors


@pytest.mark.django_db
def test_storage_cant_delete_other_users(client, user, user_factory, storage_factory):
    other_user = user_factory()
    storage_other_user = storage_factory(user=other_user)
    client.force_login(user)
    assert Storage.objects.count() == 3
    r = client.post(
        reverse("storage-delete", kwargs={"pk": storage_other_user.pk}), follow=True
    )
    assert r.status_code == HTTPStatus.NOT_FOUND
    assert Storage.objects.count() == 3


@pytest.mark.django_db
def test_storage_can_delete_multiple(client, user, storage_factory):
    client.force_login(user)
    storage_factory(user=user)
    assert Storage.objects.count() == 2
    storage = Storage.objects.first()
    r = client.post(reverse("storage-delete", kwargs={"pk": storage.pk}), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("storage-list"))
    assert Storage.objects.count() == 1


@pytest.mark.django_db
def test_unauthenticated_cant_add_stock(client, user, wine_factory):
    wine = wine_factory(user=user)
    r = client.post(reverse("stock-add", kwargs={"pk": wine.pk}), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(
        response=r,
        expected_url=reverse("account_login")
        + "?next="
        + reverse("stock-add", kwargs={"pk": wine.pk}),
    )
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="account/login.html")


@pytest.mark.django_db
def test_user_can_add_stock(client, user, wine_factory):
    client.force_login(user)
    storage = Storage.objects.first()
    wine = wine_factory(user=user)
    data = {
        "storage": storage.pk,
    }
    r = client.post(
        reverse("stock-add", kwargs={"pk": wine.pk}), data=data, follow=True
    )
    assert r.status_code == HTTPStatus.OK
    assertRedirects(
        response=r, expected_url=reverse("wine-detail", kwargs={"pk": wine.pk})
    )
    assert storage.used_slots == 1
    assert storage.items.first().wine == wine


@pytest.mark.django_db
def test_user_cant_add_stock_to_other_users_storage(
    client, user, user_factory, wine_factory
):
    storage = Storage.objects.filter(user=user).first()
    other_user = user_factory()
    other_storage = Storage.objects.filter(user=other_user).first()
    client.force_login(user)
    wine = wine_factory(user=user)
    other_wine = wine_factory(user=other_user)
    data = {
        "storage": other_storage.pk,
    }
    r = client.post(
        reverse("stock-add", kwargs={"pk": wine.pk}), data=data, follow=True
    )
    assert r.status_code == HTTPStatus.OK
    assert r.context["form"].errors
    assert other_storage.used_slots == 0
    # Trying to add stock to another user's wine returns 404 (regardless of storage)
    r = client.post(
        reverse("stock-add", kwargs={"pk": other_wine.pk}), data=data, follow=True
    )
    assert r.status_code == HTTPStatus.NOT_FOUND
    assert other_storage.used_slots == 0
    assert StorageItem.objects.count() == 0
    data = {
        "storage": storage.pk,
    }
    r = client.post(
        reverse("stock-add", kwargs={"pk": other_wine.pk}), data=data, follow=True
    )
    assert r.status_code == HTTPStatus.NOT_FOUND
    assert other_storage.used_slots == 0
    assert StorageItem.objects.count() == 0


@pytest.mark.django_db
def test_user_can_delete_stock(client, user, wine_factory, storage_item_factory):
    client.force_login(user)
    storage = Storage.objects.first()
    wine = wine_factory(user=user)
    item = storage_item_factory(storage=storage, wine=wine, user=user)
    assert item.deleted is False
    assert StorageItem.objects.count() == 1
    r = client.post(reverse("stock-delete", kwargs={"pk": item.pk}), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(
        response=r, expected_url=reverse("wine-detail", kwargs={"pk": wine.pk})
    )
    assert StorageItem.objects.count() == 1
    item.refresh_from_db()
    assert item.deleted is True
    assert item.removal_reason == StorageItem.RemovalReason.REMOVED
    assert item.finished_date == timezone.localdate()
    assert item.given_date is None
    assert item.recipient == ""
    assert item.given_occasion == ""


@pytest.mark.django_db
def test_user_cant_delete_other_users_stock(
    client, user, user_factory, wine_factory, storage_item_factory
):
    client.force_login(user)
    user2 = user_factory()
    storage = Storage.objects.filter(user=user2).first()
    wine = wine_factory(user=user2)
    item = storage_item_factory(storage=storage, wine=wine, user=user2)
    assert item.deleted is False
    assert StorageItem.objects.count() == 1
    r = client.post(reverse("stock-delete", kwargs={"pk": item.pk}), follow=True)
    assert r.status_code == HTTPStatus.NOT_FOUND
    assert StorageItem.objects.count() == 1
    item.refresh_from_db()
    assert item.deleted is False


@pytest.mark.django_db
def test_user_cant_add_to_full_slot(
    client, user, storage_factory, storage_item_factory, wine_factory
):
    storage = storage_factory(user=user, rows=1, columns=1)
    client.force_login(user)
    wine = wine_factory(user=user)
    storage_item_factory(storage=storage, wine=wine, row=1, column=1, user=user)
    data = {
        "storage": storage.pk,
        "row": 1,
        "column": 1,
    }
    r = client.post(
        reverse("stock-add", kwargs={"pk": wine.pk}), data=data, follow=True
    )
    assert r.status_code == HTTPStatus.OK
    assert r.context["form"].errors


@pytest.mark.django_db
def test_user_can_add_to_specific_slot(client, user, storage_factory, wine_factory):
    storage = storage_factory(user=user, rows=2, columns=2)
    client.force_login(user)
    wine = wine_factory(user=user)
    data = {
        "storage": storage.pk,
        "row": 2,
        "column": 1,
    }
    r = client.post(
        reverse("stock-add", kwargs={"pk": wine.pk}), data=data, follow=True
    )
    assert r.status_code == HTTPStatus.OK
    assertRedirects(
        response=r, expected_url=reverse("wine-detail", kwargs={"pk": wine.pk})
    )
    item = storage.items.first()
    assert item.wine == wine
    assert item.row == 2
    assert item.column == 1


@pytest.mark.django_db
def test_user_cant_add_to_invalid_slot(client, user, storage_factory, wine_factory):
    storage = storage_factory(user=user, rows=2, columns=2)
    client.force_login(user)
    wine = wine_factory(user=user)
    data = {
        "storage": storage.pk,
        "row": 3,
        "column": 1,
    }
    r = client.post(
        reverse("stock-add", kwargs={"pk": wine.pk}), data=data, follow=True
    )
    assert r.status_code == HTTPStatus.OK
    assert r.context["form"].errors


@pytest.mark.django_db
def test_form_context_has_empty_slots(
    client, user, storage_factory, storage_item_factory, wine_factory
):
    storage = storage_factory(user=user, rows=2, columns=2)
    client.force_login(user)
    wine = wine_factory(user=user)
    r = client.get(reverse("stock-add", kwargs={"pk": wine.pk}))
    assert r.status_code == HTTPStatus.OK
    assert r.context["free_cells_by_storage"][storage.pk] == {
        1: [1, 2],
        2: [1, 2],
    }
    storage_item_factory(storage=storage, wine=wine, row=1, column=1, user=user)
    storage_item_factory(storage=storage, wine=wine, row=2, column=2, user=user)
    r = client.get(reverse("stock-add", kwargs={"pk": wine.pk}))
    assert r.status_code == HTTPStatus.OK
    assert r.context["free_cells_by_storage"][storage.pk] == {
        1: [2],
        2: [1],
    }


@pytest.mark.django_db
def test_used_slot_is_free_after_delete(
    client, user, storage_factory, storage_item_factory, wine_factory
):
    wine = wine_factory(user=user)
    wine_new = wine_factory(user=user)
    storage = storage_factory(user=user, rows=2, columns=2)
    storage_item_factory(
        storage=storage, wine=wine, row=1, column=1, user=user, deleted=True
    )
    client.force_login(user)
    data = {
        "storage": storage.pk,
        "row": 1,
        "column": 1,
    }
    r = client.post(
        reverse("stock-add", kwargs={"pk": wine_new.pk}), data=data, follow=True
    )
    assert r.status_code == HTTPStatus.OK
    assertRedirects(
        response=r, expected_url=reverse("wine-detail", kwargs={"pk": wine_new.pk})
    )
    item = storage.items.filter(deleted=False).first()
    assert item.wine == wine_new
    assert item.row == 1
    assert item.column == 1
    assert item.deleted is False


@pytest.mark.django_db
def test_bottle_history_shows_move_positions(
    client, user, wine_factory, storage_item_factory
):
    wine = wine_factory(user=user)
    storage = user.storage_set.first()
    bottle = storage_item_factory(
        wine=wine,
        storage=storage,
        user=user,
        row=1,
        column=1,
    )
    BottleMoveHistory.objects.create(
        storage_item=bottle,
        from_storage=storage,
        from_row=1,
        from_column=1,
        to_storage=storage,
        to_row=2,
        to_column=3,
        user=user,
    )
    bottle.row = 2
    bottle.column = 3
    bottle.save(update_fields=["row", "column"])

    client.force_login(user)
    r = client.get(reverse("bottle-history", kwargs={"pk": bottle.pk}))
    content = r.content.decode()

    assert r.status_code == HTTPStatus.OK
    assert "Moved" in content
    assert "Row 1, Cell 1" in content
    assert "Row 2, Cell 3" in content


@pytest.mark.django_db
def test_bottle_history_shows_moves_between_storages(
    client, user, wine_factory, storage_item_factory, storage_factory
):
    wine = wine_factory(user=user)
    source_storage = user.storage_set.first()
    target_storage = storage_factory(user=user, name="Archive Rack")
    bottle = storage_item_factory(
        wine=wine,
        storage=source_storage,
        user=user,
        row=1,
        column=1,
    )
    BottleMoveHistory.objects.create(
        storage_item=bottle,
        from_storage=source_storage,
        from_row=1,
        from_column=1,
        to_storage=target_storage,
        to_row=2,
        to_column=3,
        user=user,
    )
    bottle.storage = target_storage
    bottle.row = 2
    bottle.column = 3
    bottle.save(update_fields=["storage", "row", "column"])

    client.force_login(user)
    r = client.get(reverse("bottle-history", kwargs={"pk": bottle.pk}))
    content = r.content.decode()

    assert r.status_code == HTTPStatus.OK
    assert source_storage.name in content
    assert target_storage.name in content
    assert "Row 1, Cell 1" in content
    assert "Row 2, Cell 3" in content


@pytest.mark.django_db
def test_consumed_bottle_history_links_back_to_consumed_bottles(
    client, user, wine_factory, storage_item_factory
):
    wine = wine_factory(user=user)
    storage = user.storage_set.first()
    bottle = storage_item_factory(
        wine=wine,
        storage=storage,
        user=user,
        deleted=True,
        finished_date=date(2025, 1, 5),
    )

    client.force_login(user)
    r = client.get(reverse("bottle-history", kwargs={"pk": bottle.pk}))
    content = r.content.decode()
    expected_href = (
        f'href="{reverse("wine-detail", kwargs={"pk": wine.pk})}'
        "?show_consumed=1#consumed-bottles"
    )

    assert r.status_code == HTTPStatus.OK
    assert expected_href in content


@pytest.mark.django_db
def test_bottle_history_shows_quick_log_for_active_bottle(
    client, user, wine_factory, storage_item_factory
):
    wine = wine_factory(user=user)
    storage = user.storage_set.first()
    bottle = storage_item_factory(wine=wine, storage=storage, user=user)

    client.force_login(user)
    response = client.get(reverse("bottle-history", kwargs={"pk": bottle.pk}))

    assert response.status_code == HTTPStatus.OK
    assert (
        reverse("bottle-quick-log", kwargs={"pk": bottle.pk})
        in response.content.decode()
    )
    assert "Just drank this" in response.content.decode()


@pytest.mark.django_db
def test_bottle_quick_log_creates_record_and_consumes_bottle(
    client, user, wine_factory, storage_item_factory
):
    from wine_cellar.apps.wine.models import DrinkRecord

    wine = wine_factory(user=user)
    storage = user.storage_set.first()
    bottle = storage_item_factory(wine=wine, storage=storage, user=user)

    client.force_login(user)
    response = client.post(reverse("bottle-quick-log", kwargs={"pk": bottle.pk}))

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("bottle-history", kwargs={"pk": bottle.pk})

    record = DrinkRecord.objects.get(storage_item=bottle)
    assert record.wine == wine
    assert record.user == user
    assert record.household == user.user_settings.active_household
    assert record.date_consumed == timezone.localdate()
    assert record.rating is None
    assert record.tasting_notes in (None, "")

    bottle.refresh_from_db()
    assert bottle.deleted is True
    assert bottle.finished_date == timezone.localdate()
    assert bottle.removal_reason == StorageItem.RemovalReason.CONSUMED


@pytest.mark.django_db
def test_bottle_quick_log_rejects_repeat_posts_for_consumed_bottle(
    client, user, wine_factory, storage_item_factory
):
    from wine_cellar.apps.wine.models import DrinkRecord

    wine = wine_factory(user=user)
    storage = user.storage_set.first()
    bottle = storage_item_factory(wine=wine, storage=storage, user=user)

    client.force_login(user)
    first_response = client.post(reverse("bottle-quick-log", kwargs={"pk": bottle.pk}))
    second_response = client.post(reverse("bottle-quick-log", kwargs={"pk": bottle.pk}))

    assert first_response.status_code == HTTPStatus.FOUND
    assert second_response.status_code == HTTPStatus.NOT_FOUND
    assert DrinkRecord.objects.filter(storage_item=bottle).count() == 1


@pytest.mark.django_db
def test_mark_bottle_as_given_records_recipient_and_date(
    client, user, wine_factory, storage_item_factory
):
    wine = wine_factory(user=user)
    storage = user.storage_set.first()
    bottle = storage_item_factory(wine=wine, storage=storage, user=user)

    client.force_login(user)
    response = client.post(
        reverse("stock-give", kwargs={"pk": bottle.pk}),
        {
            "recipient": "Alex",
            "given_date": "2026-04-16",
            "given_occasion": "Birthday",
        },
    )

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("wine-detail", kwargs={"pk": wine.pk})

    bottle.refresh_from_db()
    assert bottle.deleted is True
    assert bottle.removal_reason == StorageItem.RemovalReason.GIVEN
    assert bottle.recipient == "Alex"
    assert bottle.given_date == date(2026, 4, 16)
    assert bottle.given_occasion == "Birthday"
    assert bottle.finished_date is None


@pytest.mark.django_db
def test_given_bottle_history_links_back_to_gifted_bottles(
    client, user, wine_factory, storage_item_factory
):
    wine = wine_factory(user=user)
    storage = user.storage_set.first()
    bottle = storage_item_factory(
        wine=wine,
        storage=storage,
        user=user,
        deleted=True,
        removal_reason=StorageItem.RemovalReason.GIVEN,
        recipient="Chris",
        given_occasion="Retirement",
        given_date=date(2025, 1, 5),
    )

    client.force_login(user)
    r = client.get(reverse("bottle-history", kwargs={"pk": bottle.pk}))
    content = r.content.decode()
    expected_href = (
        f'href="{reverse("wine-detail", kwargs={"pk": wine.pk})}'
        "?show_consumed=1#gifted-bottles"
    )

    assert r.status_code == HTTPStatus.OK
    assert expected_href in content
    assert "Given away" in content
    assert "Chris" in content


@pytest.mark.django_db
def test_broken_or_lost_bottle_history_shows_broken_or_lost_label(
    client, user, wine_factory, storage_item_factory
):
    wine = wine_factory(user=user)
    storage = user.storage_set.first()
    bottle = storage_item_factory(
        wine=wine,
        storage=storage,
        user=user,
        deleted=True,
        removal_reason=StorageItem.RemovalReason.REMOVED,
        finished_date=date(2025, 1, 5),
    )

    client.force_login(user)
    response = client.get(reverse("bottle-history", kwargs={"pk": bottle.pk}))
    content = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert "Broken or lost" in content
