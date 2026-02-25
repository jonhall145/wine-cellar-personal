import datetime
import json
from http import HTTPStatus

import pytest
from django.urls import reverse
from pytest_django.asserts import assertRedirects, assertTemplateUsed

from wine_cellar.apps.whisky.models import FillLevel, Whisky, WhiskyDrinkRecord


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
    assertTemplateUsed(response=r, template_name="whisky/homepage.html")


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
    assertTemplateUsed(response=r, template_name="whisky/whisky_list.html")


@pytest.mark.django_db
def test_whisky_list_shows_user_whiskies(client, user, whisky_factory):
    """Test that whisky list shows whiskies belonging to the user."""
    whisky = whisky_factory(user=user, name="Lagavulin 16")
    client.force_login(user)
    r = client.get(reverse("whisky-list"))
    assert r.status_code == HTTPStatus.OK
    assert whisky in r.context["whiskies"]


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
    assert "form" in r.context


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
    assertTemplateUsed(response=r, template_name="whisky/whisky_confirm_delete.html")

    # POST deletes the whisky
    r = client.post(reverse("whisky-delete", kwargs={"pk": whisky_pk}), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("whisky-list"))
    assert not Whisky.objects.filter(pk=whisky_pk).exists()


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
