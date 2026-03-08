import datetime
import json
from http import HTTPStatus

import pytest
from django.urls import reverse
from pytest_django.asserts import assertRedirects, assertTemplateUsed

from wine_cellar.apps.whisky.models import (
    Collection,
    FillLevel,
    Whisky,
    WhiskyDrinkRecord,
)


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
def test_whisky_list_shows_user_whiskies(client, user, whisky_factory):
    """Test that whisky list shows whiskies belonging to the user."""
    whisky = whisky_factory(user=user, name="Lagavulin 16")
    client.force_login(user)
    r = client.get(reverse("whisky-list"))
    assert r.status_code == HTTPStatus.OK
    assert whisky in r.context["whiskies"]


@pytest.mark.django_db
def test_whisky_filter_by_collection(client, user, whisky_factory):
    whisky_in_collection = whisky_factory(user=user)
    whisky_outside_collection = whisky_factory(user=user)
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
    assertTemplateUsed(response=r, template_name="core/confirm_delete.html")

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
