from http import HTTPStatus

import pytest
from django.urls import reverse
from pytest_django.asserts import (
    assertRedirects,
    assertTemplateNotUsed,
    assertTemplateUsed,
)

from wine_cellar.apps.wine.models import Collection, Wine, WineBarcode


@pytest.mark.django_db
def test_homepage_unauthenticated(client):
    r = client.get(reverse("homepage"), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("account_login") + "?next=/")
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="account/login.html")


@pytest.mark.django_db
def test_homepage(client, user):
    client.force_login(user)
    r = client.get(reverse("homepage"), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="core/homepage.html")
    assertTemplateNotUsed(response=r, template_name="account/login.html")


@pytest.mark.django_db
def test_base_template_includes_skip_link(client, user):
    client.force_login(user)
    r = client.get(reverse("homepage"), follow=True)
    assert r.status_code == HTTPStatus.OK
    content = r.content.decode()
    assert 'href="#main-content"' in content
    assert 'id="main-content"' in content


@pytest.mark.django_db
def test_homepage_stats(client, user, wine_factory, storage_item_factory):
    Wine.objects.filter(user=user).delete()
    wine = wine_factory(user=user, vintage=2020)
    storage = user.storage_set.first()
    wine_2 = wine_factory(user=user, country="DE", vintage=2023, price=15.00)
    wine_factory(user=user, country="ES", vintage=2024)
    storage_item_factory(wine=wine, storage=storage, price=10.50)
    storage_item_factory(wine=wine, storage=storage, price=5.25)
    storage_item_factory(wine=wine, storage=storage, price=8.99, deleted=True)
    storage_item_factory(wine=wine_2, storage=storage, price=4.99, deleted=True)
    storage_item_factory(wine=wine_2, storage=storage, price=12.00)
    storage_item_factory(wine=wine_2, storage=storage)
    client.force_login(user)
    r = client.get(reverse("homepage"), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="core/homepage.html")
    assertTemplateNotUsed(response=r, template_name="registration/login.html")
    assert r.context_data["oldest"] == 2020
    assert r.context_data["youngest"] == 2024
    # we only count wines in stock, not bottles
    assert r.context_data["wines_in_stock"] == 2
    assert r.context_data["wines"] == 3
    assert r.context_data["countries"] == 2
    assert r.context_data["total_value"] == "€43"


@pytest.mark.django_db
def test_wine_create_unauthenticated(client, user):
    r = client.get(reverse("wine-add"), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(
        response=r,
        expected_url=reverse("account_login") + "?next=" + reverse("wine-add"),
    )
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="account/login.html")


@pytest.mark.django_db
def test_wine_create(client, user):
    client.force_login(user)
    r = client.get(reverse("wine-add"), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="wine_create.html")
    assertTemplateUsed(response=r, template_name="core/beverage_create.html")


@pytest.mark.django_db
def test_wine_create_with_grapes(client, user, grape_factory):
    grape1 = grape_factory()
    grape2 = grape_factory()
    client.force_login(user)
    r = client.get(reverse("wine-add"), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="wine_create.html")
    f = r.context["form"]
    grapes = [pk for pk, name in f.fields["grapes"].choices]
    assert len(grapes) == 2
    assert grape1.pk in grapes
    assert grape2.pk in grapes


@pytest.mark.django_db
def test_wine_create_post_empty(client, user):
    client.force_login(user)
    data = {}
    r = client.post(reverse("wine-add"), data)
    assert r.status_code == HTTPStatus.OK
    f = r.context["form"]
    assert not f.is_valid()
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="wine_create.html")
    assert not Wine.objects.exists()


@pytest.mark.django_db
def test_wine_create_post_unauthenticated(client):
    r = client.post(reverse("wine-add"), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(
        response=r,
        expected_url=reverse("account_login") + "?next=" + reverse("wine-add"),
    )
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="account/login.html")
    assert not Wine.objects.exists()


@pytest.mark.django_db
def test_wine_create_post_with_barcode(client, user):
    client.force_login(user)

    data = {
        "name": "Merlot",
        "wine_type": "RE",
        "category": "DR",
        "abv": 13.0,
        "size": "ST",
        "vintage": 2002,
        "country": "DE",
        "form_step": 4,
    }
    assert not Wine.objects.exists()
    r = client.get(reverse("wine-add", kwargs={"code": 12345}))
    initial = r.context_data["form"].initial.copy()
    initial.update(data)
    r = client.post(
        reverse("wine-add", kwargs={"code": 12345}), data=initial, follow=True
    )
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("wine-list"))
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="core/beverage_list.html")
    assert Wine.objects.exists()
    wine = Wine.objects.first()
    assert wine.name == data["name"]
    assert wine.wine_type == data["wine_type"]
    assert wine.abv == data["abv"]
    assert wine.size.name == "ST"
    assert wine.vintage == data["vintage"]
    assert wine.barcodes.filter(barcode="12345").exists()


@pytest.mark.django_db
def test_wine_create_post_with_drinking_window(client, user):
    client.force_login(user)

    data = {
        "name": "Merlot",
        "wine_type": "RE",
        "category": "DR",
        "abv": 13.0,
        "size": "ST",
        "vintage": 2002,
        "drink_from": 2025,
        "drink_to": 2030,
        "country": "DE",
        "form_step": 4,
    }
    assert not Wine.objects.exists()
    r = client.get(reverse("wine-add", kwargs={"code": 12345}))
    initial = r.context_data["form"].initial.copy()
    initial.update(data)
    r = client.post(
        reverse("wine-add", kwargs={"code": 12345}), data=initial, follow=True
    )
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("wine-list"))
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="core/beverage_list.html")
    assert Wine.objects.exists()
    wine = Wine.objects.first()
    assert wine.name == data["name"]
    assert wine.wine_type == data["wine_type"]
    assert wine.abv == data["abv"]
    assert wine.size.name == "ST"
    assert wine.vintage == data["vintage"]
    assert wine.barcodes.filter(barcode="12345").exists()
    assert wine.drink_from == 2025
    assert wine.drink_to == 2030


@pytest.mark.django_db
def test_wine_create_post_with_drinking_window_now(client, user):
    """Test creating wine with 'now' (0) for drink_from."""
    client.force_login(user)

    data = {
        "name": "Merlot",
        "wine_type": "RE",
        "category": "DR",
        "abv": 13.0,
        "size": "ST",
        "vintage": 2002,
        "drink_from": 0,  # "Now"
        "drink_to": 2030,
        "country": "DE",
        "form_step": 4,
    }
    assert not Wine.objects.exists()
    r = client.get(reverse("wine-add", kwargs={"code": 12345}))
    initial = r.context_data["form"].initial.copy()
    initial.update(data)
    r = client.post(
        reverse("wine-add", kwargs={"code": 12345}), data=initial, follow=True
    )
    assert r.status_code == HTTPStatus.OK
    assert Wine.objects.exists()
    wine = Wine.objects.first()
    assert wine.drink_from == 0
    assert wine.drink_to == 2030


@pytest.mark.django_db
def test_wine_create_post_single_page(client, user):
    """Test creating wine with single-page form (no steps)."""
    client.force_login(user)

    data = {
        "name": "Merlot",
        "wine_type": "RE",
        "size": "ST",
        "country": "DE",
        "category": "DR",
        "abv": 13.0,
        "vintage": 2002,
        "rating": 2,
        "comment": "Good wine",
    }
    assert not Wine.objects.exists()
    r = client.get(reverse("wine-add"))
    initial = r.context_data["form"].initial.copy()
    initial.update(data)
    r = client.post(reverse("wine-add"), data=initial, follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("wine-list"))
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="core/beverage_list.html")
    assert Wine.objects.exists()
    wine = Wine.objects.first()
    assert wine.name == data["name"]
    assert wine.wine_type == data["wine_type"]
    assert wine.abv == data["abv"]
    assert wine.size.name == "ST"
    assert wine.vintage == data["vintage"]
    assert wine.comment == data["comment"]
    assert wine.rating == data["rating"]


@pytest.mark.django_db
def test_wine_create_post_invalid_step(client, user):
    client.force_login(user)

    data = {
        "name": "Merlot",
        "wine_type": "RE",
        "category": "DR",
        "abv": 13.0,
        "size": "ST",
        "vintage": 2002,
        "country": "DE",
        "form_step": 5,
    }
    assert not Wine.objects.exists()
    r = client.post(reverse("wine-add"), data, follow=True)
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="wine_create.html")
    assert r.context_data["form"].errors
    assert not Wine.objects.exists()


@pytest.mark.django_db
def test_wine_create_post_valid(client, user):
    client.force_login(user)

    data = {
        "name": "Merlot",
        "wine_type": "RE",
        "category": "DR",
        "abv": 13.0,
        "size": "ST",
        "vintage": 2002,
        "country": "DE",
    }
    assert not Wine.objects.exists()
    r = client.post(reverse("wine-add"), data, follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("wine-list"))
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="core/beverage_list.html")
    assert Wine.objects.exists()
    wine = Wine.objects.first()
    assert wine.name == data["name"]
    assert wine.wine_type == data["wine_type"]
    assert wine.abv == data["abv"]
    assert wine.size.name == "ST"
    assert wine.vintage == data["vintage"]


@pytest.mark.django_db
def test_wine_create_post_duplicate_handled_gracefully(client, user):
    """Test that adding a duplicate wine doesn't cause a 500 error."""
    client.force_login(user)

    data = {
        "name": "Duplicate Wine",
        "wine_type": "RE",
        "category": "DR",
        "abv": 13.0,
        "size": "ST",
        "vintage": 2020,
        "country": "FR",
    }

    # First submission should create the wine
    r = client.post(reverse("wine-add"), data, follow=True)
    assert r.status_code == HTTPStatus.OK
    assert Wine.objects.count() == 1
    first_wine = Wine.objects.first()

    # Second submission with same data should NOT cause 500 error
    r = client.post(reverse("wine-add"), data, follow=True)
    assert r.status_code == HTTPStatus.OK  # Should be 200, not 500
    assertRedirects(response=r, expected_url=reverse("wine-list"))

    # Should still have only one wine (not duplicated)
    assert Wine.objects.count() == 1
    assert Wine.objects.first().pk == first_wine.pk

    # Should have info message about wine already existing
    messages = list(r.context["messages"])
    assert len(messages) == 1
    assert "already exists" in messages[0].message.lower()


@pytest.mark.django_db
def test_wine_create_post_single_grape_valid(client, user, grape_factory):
    grape1 = grape_factory()
    grape_factory()

    client.force_login(user)
    data = {
        "name": "Wine Single Grape",
        "wine_type": "RE",
        "category": "DR",
        "abv": 13.0,
        "size": "ST",
        "vintage": 2002,
        "grapes": grape1.pk,
        "country": "DE",
    }
    assert not Wine.objects.exists()
    r = client.post(reverse("wine-add"), data, follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("wine-list"))
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="core/beverage_list.html")
    assert Wine.objects.exists()
    wine = Wine.objects.first()
    assert wine.name == data["name"]
    assert wine.wine_type == data["wine_type"]
    assert wine.abv == data["abv"]
    assert wine.size.name == "ST"
    assert wine.vintage == data["vintage"]
    assert wine.grapes.count() == 1
    assert wine.grapes.first() == grape1


@pytest.mark.django_db
def test_wine_create_post_multiple_grape_valid(client, user, grape_factory):
    grape1 = grape_factory()
    grape2 = grape_factory()

    client.force_login(user)
    data = {
        "name": "Wine Single Grape",
        "wine_type": "RE",
        "category": "DR",
        "abv": 13.0,
        "size": "ST",
        "vintage": 2002,
        "grapes": [grape1.pk, grape2.pk],
        "country": "DE",
    }
    assert not Wine.objects.exists()
    r = client.post(reverse("wine-add"), data, follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("wine-list"))
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="core/beverage_list.html")
    assert Wine.objects.exists()
    wine = Wine.objects.first()
    assert wine.name == data["name"]
    assert wine.wine_type == data["wine_type"]
    assert wine.abv == data["abv"]
    assert wine.size.name == "ST"
    assert wine.vintage == data["vintage"]
    assert wine.grapes.count() == 2
    assert wine.grapes.filter(id__in=[grape1.pk, grape2.pk])


@pytest.mark.django_db
def test_wine_create_post_new_grape_valid(client, user, grape_factory):

    client.force_login(user)
    data = {
        "name": "Wine Single Grape",
        "wine_type": "RE",
        "category": "DR",
        "abv": 13.0,
        "size": "ST",
        "vintage": 2002,
        "grapes": "tom_new_optTestGrape",
        "country": "DE",
    }
    assert not Wine.objects.exists()
    r = client.post(reverse("wine-add"), data, follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("wine-list"))
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="core/beverage_list.html")
    assert Wine.objects.exists()
    wine = Wine.objects.first()
    assert wine.name == data["name"]
    assert wine.wine_type == data["wine_type"]
    assert wine.abv == data["abv"]
    assert wine.size.name == "ST"
    assert wine.vintage == data["vintage"]
    assert wine.grapes.count() == 1
    assert wine.grapes.first().name == "TestGrape"


@pytest.mark.django_db
def test_wine_create_post_invalid_grape(client, user, grape_factory):
    client.force_login(user)

    data = {
        "name": "Wine Single Grape",
        "wine_type": "RE",
        "category": "DR",
        "abv": 13.0,
        "size": "ST",
        "vintage": 2002,
        "grapes": [1.0],
        "country": "DE",
    }
    assert not Wine.objects.exists()
    r = client.post(reverse("wine-add"), data, follow=True)
    assert r.status_code == HTTPStatus.OK
    f = r.context["form"]
    assert not f.is_valid()
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="wine_create.html")
    assert not Wine.objects.exists()
    data = {
        "name": "Wine Single Grape",
        "wine_type": "RE",
        "category": "DR",
        "abv": 13.0,
        "size": "ST",
        "vintage": 2002,
        "grapes": 1,
        "country": "DE",
    }
    assert not Wine.objects.exists()
    r = client.post(reverse("wine-add"), data, follow=True)
    assert r.status_code == HTTPStatus.OK
    f = r.context["form"]
    assert not f.is_valid()
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="wine_create.html")
    assert not Wine.objects.exists()


@pytest.mark.django_db
def test_wine_create_post_new_grape_multiple_valid(client, user, grape_factory):
    grape1 = grape_factory()
    grape2 = grape_factory()

    client.force_login(user)
    data = {
        "name": "Wine Single Grape",
        "wine_type": "RE",
        "category": "DR",
        "abv": 13.0,
        "size": "ST",
        "vintage": 2002,
        "grapes": ["tom_new_optTestGrape", grape1.pk, grape2.pk],
        "country": "DE",
    }
    assert not Wine.objects.exists()
    r = client.post(reverse("wine-add"), data, follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("wine-list"))
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="core/beverage_list.html")
    assert Wine.objects.exists()
    wine = Wine.objects.first()
    assert wine.name == data["name"]
    assert wine.wine_type == data["wine_type"]
    assert wine.abv == data["abv"]
    assert wine.size.name == "ST"
    assert wine.vintage == data["vintage"]
    assert wine.grapes.count() == 3
    assert wine.grapes.filter(id__in=[grape1.pk, grape2.pk])
    assert wine.grapes.filter(name="TestGrape")


@pytest.mark.django_db
def test_wine_create_post_all_valid_fields(
    client,
    user,
    grape_factory,
    food_pairing_factory,
    source_factory,
    attribute_factory,
    vineyard_factory,
):
    grape1 = grape_factory()
    grape_factory()
    food_pairing = food_pairing_factory()
    source = source_factory()
    vineyard = vineyard_factory()
    attribute = attribute_factory()

    client.force_login(user)
    data = {
        "name": "Wine All",
        "wine_type": "RE",
        "category": "DR",
        "abv": 13.0,
        "size": "ST",
        "vintage": 2002,
        "grapes": grape1.pk,
        "food_pairings": food_pairing.pk,
        "source": source.pk,
        "vineyard": vineyard.pk,
        "attributes": attribute.pk,
        "country": "DE",
    }
    assert not Wine.objects.exists()
    r = client.post(reverse("wine-add"), data, follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("wine-list"))
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="core/beverage_list.html")
    assert Wine.objects.exists()
    wine = Wine.objects.first()
    assert wine.name == data["name"]
    assert wine.wine_type == data["wine_type"]
    assert wine.abv == data["abv"]
    assert wine.size.name == "ST"
    assert wine.vintage == data["vintage"]
    assert wine.grapes.count() == 1
    assert wine.grapes.first() == grape1
    assert wine.food_pairings.count() == 1
    assert wine.food_pairings.first() == food_pairing
    assert wine.vineyard.count() == 1
    assert wine.vineyard.first() == vineyard
    assert wine.source.count() == 1
    assert wine.source.first() == source
    assert wine.attributes.count() == 1


@pytest.mark.django_db
def test_wine_update_valid_fields(
    client,
    user,
    wine,
    grape_factory,
    food_pairing_factory,
    source_factory,
    attribute_factory,
    vineyard_factory,
):
    grape1 = grape_factory()
    grape_factory()
    food_pairing = food_pairing_factory()
    source = source_factory()
    vineyard = vineyard_factory()
    attribute = attribute_factory()

    client.force_login(user)
    data = {
        "name": wine.name,
        "wine_type": "RE",
        "category": "DR",
        "abv": 13.0,
        "size": "ST",
        "vintage": 2002,
        "grapes": grape1.pk,
        "food_pairings": food_pairing.pk,
        "source": source.pk,
        "vineyard": vineyard.pk,
        "attributes": attribute.pk,
        "country": "DE",
    }
    r = client.post(reverse("wine-edit", kwargs={"pk": wine.pk}), data, follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(
        response=r, expected_url=reverse("wine-detail", kwargs={"pk": wine.pk})
    )
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="wine_detail.html")
    changed_wine = Wine.objects.first()
    assert changed_wine.name == wine.name
    assert changed_wine.wine_type == data["wine_type"]
    assert changed_wine.abv == data["abv"]
    assert changed_wine.size.name == "ST"
    assert changed_wine.vintage == data["vintage"]
    assert changed_wine.grapes.count() == 1
    assert changed_wine.grapes.first() == grape1
    assert changed_wine.food_pairings.count() == 1
    assert changed_wine.food_pairings.first() == food_pairing
    assert changed_wine.vineyard.count() == 1
    assert changed_wine.vineyard.first() == vineyard
    assert changed_wine.source.count() == 1
    assert changed_wine.source.first() == source
    assert changed_wine.attributes.count() == 1


@pytest.mark.django_db
def test_wine_soft_delete(client, user, wine_factory):
    """Test that deleting a wine soft-deletes it instead of removing from DB."""
    wine = wine_factory(user=user, name="SoftDeleteMe")
    wine_pk = wine.pk
    client.force_login(user)

    # GET shows confirmation page
    r = client.get(reverse("wine-delete", kwargs={"pk": wine_pk}))
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="core/confirm_delete.html")

    # POST soft-deletes the wine
    r = client.post(reverse("wine-delete", kwargs={"pk": wine_pk}), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("wine-list"))
    # Soft delete: record still exists in DB but is marked deleted
    assert Wine.objects.filter(pk=wine_pk, deleted=True).exists()
    assert not Wine.objects.filter(pk=wine_pk, deleted=False).exists()


@pytest.mark.django_db
def test_soft_deleted_wine_hidden_from_list(client, user, wine_factory):
    """Test that soft-deleted wines don't appear in the wine list."""
    wine = wine_factory(user=user, name="HiddenWine")
    wine.deleted = True
    wine.save(update_fields=["deleted"])
    client.force_login(user)

    r = client.get(reverse("wine-list"))
    assert r.status_code == HTTPStatus.OK
    assert wine not in r.context["object_list"]


@pytest.mark.django_db
def test_wine_scanned_existing(
    client,
    user,
    wine_factory,
):
    wine = wine_factory(user=user, country="DE")
    WineBarcode.objects.create(
        wine=wine, barcode="12345", user=user, household=wine.household
    )
    client.force_login(user)
    r = client.get(reverse("wine-scan", kwargs={"code": "12345"}), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(
        response=r, expected_url=reverse("wine-detail", kwargs={"pk": wine.pk})
    )
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="wine_detail.html")


@pytest.mark.django_db
def test_wine_scanned_non_existing(
    client,
    user,
    wine_factory,
):
    wine = wine_factory(user=user, country="DE")
    WineBarcode.objects.create(
        wine=wine, barcode="12345", user=user, household=wine.household
    )
    client.force_login(user)
    r = client.get(reverse("wine-scan", kwargs={"code": "00000"}), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="core/scanned_beverage.html")


@pytest.mark.django_db
def test_per_page_option_values_are_relative_querystrings(
    client, user, wine_factory, storage_item_factory
):
    """Per-page option values must be relative querystrings that preserve the path.

    Regression test: the per-page JS used new URL(value, window.location.origin)
    which dropped the /wines/ path, redirecting to /?per_page=50 instead of
    /wines/?per_page=50. Ensure option values start with '?' (relative) and
    include existing filter params like stock=1.
    """
    import re

    storage = user.storage_set.first()
    wine = wine_factory(user=user)
    storage_item_factory(storage=storage, wine=wine)
    client.force_login(user)

    # Request with an active filter so we can verify it's preserved
    r = client.get(reverse("wine-list") + "?stock=1")
    assert r.status_code == HTTPStatus.OK

    content = r.content.decode()
    # Extract all option values from the per-page select
    option_values = re.findall(
        r'<select id="per-page"[^>]*>.*?</select>', content, re.DOTALL
    )
    assert option_values, "Per-page select not found in response"
    values = re.findall(r'<option value="([^"]*)"', option_values[0])
    assert len(values) >= 2, f"Expected multiple per-page options, got {values}"

    for val in values:
        # Must be a relative querystring, not an absolute URL
        assert val.startswith("?"), f"Option value should start with '?', got: {val}"
        # Must preserve existing filter params
        assert "stock=1" in val, f"Option value should preserve stock=1 filter: {val}"
        assert "per_page=" in val, f"Option value should contain per_page param: {val}"
        assert "page=1" in val, f"Option value should reset to page=1: {val}"


@pytest.mark.django_db
def test_per_page_option_values_include_js_using_location_href(
    client, user, wine_factory
):
    """The per-page JS must use window.location.href (not .origin) as URL base.

    Regression test: using window.location.origin loses the current path,
    so ?per_page=50 resolves to the site root instead of the current page.
    """
    wine_factory(user=user)
    client.force_login(user)

    r = client.get(reverse("wine-list"))
    assert r.status_code == HTTPStatus.OK

    content = r.content.decode()
    assert "new URL(value, window.location.href)" in content, (
        "Per-page JS must use window.location.href as base URL, "
        "not window.location.origin (which drops the path)"
    )
    assert "new URL(value, window.location.origin)" not in content


@pytest.mark.django_db
def test_wine_filter_in_stock(client, user, wine_factory, storage_item_factory):
    storage = user.storage_set.first()
    wine_in_stock = wine_factory(user=user, vintage=2020)
    wine_was_in_stock = wine_factory(user=user, vintage=2019)
    wine_not_in_stock = wine_factory(user=user, vintage=2021)
    storage_item_factory(storage=storage, wine=wine_in_stock)
    storage_item_factory(
        storage=storage,
        wine=wine_was_in_stock,
        deleted=True,
    )
    client.force_login(user)
    r = client.get(reverse("wine-list"))
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="core/beverage_list.html")
    assert list(r.context_data["wines"]) == [wine_in_stock]
    r = client.get(reverse("wine-list") + "?stock=0")
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="core/beverage_list.html")
    assert set(r.context_data["wines"]) == {
        wine_in_stock,
        wine_not_in_stock,
        wine_was_in_stock,
    }
    r = client.get(reverse("wine-list") + "?stock=1")
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="core/beverage_list.html")
    assert list(r.context_data["wines"]) == [wine_in_stock]


@pytest.mark.django_db
def test_wine_filter_price(client, user, wine_factory, storage_item_factory):
    Wine.objects.filter(user=user).delete()
    storage = user.storage_set.first()
    wine_in_stock_cheap = wine_factory(user=user, vintage=2020)
    wine_in_stock_expensive = wine_factory(user=user, vintage=2020)
    wine_in_stock_middle = wine_factory(user=user, vintage=2020)
    wine_was_in_stock = wine_factory(user=user, vintage=2019)
    wine_no_price = wine_factory(user=user, vintage=2019)
    wine_not_in_stock = wine_factory(user=user, vintage=2021, price=7.00)
    storage_item_factory(storage=storage, wine=wine_in_stock_cheap, price=5.00)
    storage_item_factory(storage=storage, wine=wine_in_stock_middle, price=15.00)
    storage_item_factory(storage=storage, wine=wine_in_stock_expensive, price=50.00)
    storage_item_factory(
        storage=storage,
        wine=wine_was_in_stock,
        price=10.00,
        deleted=True,
    )
    client.force_login(user)
    r = client.get(
        reverse("wine-list") + "?order=-effective_price&stock=0", follow=True
    )
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="core/beverage_list.html")
    assert list(r.context_data["wines"]) == [
        wine_in_stock_expensive,
        wine_in_stock_middle,
        wine_was_in_stock,
        wine_not_in_stock,
        wine_in_stock_cheap,
        wine_no_price,
    ]
    r = client.get(reverse("wine-list") + "?order=effective_price&stock=0", follow=True)
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="core/beverage_list.html")
    assert list(r.context_data["wines"]) == [
        wine_in_stock_cheap,
        wine_not_in_stock,
        wine_was_in_stock,
        wine_in_stock_middle,
        wine_in_stock_expensive,
        wine_no_price,
    ]


@pytest.mark.django_db
def test_wine_filter_by_collection(client, user, wine_factory, storage_item_factory):
    wine_in_collection = wine_factory(user=user)
    wine_outside_collection = wine_factory(user=user)
    storage_item_factory(wine=wine_in_collection, user=user)
    storage_item_factory(wine=wine_outside_collection, user=user)
    collection = Collection.objects.create(
        name="Dinner Party",
        user=user,
        household=wine_in_collection.household,
    )
    collection.wines.add(wine_in_collection)

    client.force_login(user)
    r = client.get(reverse("wine-list") + f"?collection={collection.pk}")

    assert r.status_code == HTTPStatus.OK
    assert list(r.context_data["wines"]) == [wine_in_collection]
    assert wine_outside_collection not in r.context_data["wines"]


@pytest.mark.django_db
def test_wine_collection_add_and_remove(client, user, wine_factory):
    wine = wine_factory(user=user)
    collection = Collection.objects.create(
        name="Summer Drinking",
        user=user,
        household=wine.household,
    )

    client.force_login(user)
    add_url = reverse("wine-collection-add", kwargs={"pk": wine.pk})
    remove_url = reverse(
        "wine-collection-remove",
        kwargs={"pk": wine.pk, "collection_pk": collection.pk},
    )

    add_response = client.post(
        add_url, data={"collection_id": collection.pk}, follow=True
    )
    assert add_response.status_code == HTTPStatus.OK
    assert collection.wines.filter(pk=wine.pk).exists()

    remove_response = client.post(remove_url, follow=True)
    assert remove_response.status_code == HTTPStatus.OK
    assert not collection.wines.filter(pk=wine.pk).exists()


@pytest.mark.django_db
def test_wine_collection_create_new_by_name(client, user, wine_factory):
    wine = wine_factory(user=user)
    client.force_login(user)
    url = reverse("wine-collection-add", kwargs={"pk": wine.pk})

    response = client.post(
        url, data={"new_collection_name": "Party Picks"}, follow=True
    )
    assert response.status_code == HTTPStatus.OK
    assert Collection.objects.filter(
        name="Party Picks", household=wine.household
    ).exists()
    collection = Collection.objects.get(name="Party Picks", household=wine.household)
    assert collection.wines.filter(pk=wine.pk).exists()


@pytest.mark.django_db
def test_wine_collection_add_invalid_id(client, user, wine_factory):
    wine = wine_factory(user=user)
    client.force_login(user)
    url = reverse("wine-collection-add", kwargs={"pk": wine.pk})

    response = client.post(url, data={"collection_id": "abc"}, follow=True)
    assert response.status_code == HTTPStatus.OK


@pytest.mark.django_db
def test_drink_record_with_bottle_selection_marks_deleted(
    client, user, wine_factory, storage_item_factory
):
    """Test recording a drink with bottle selection marks bottle as deleted."""
    from wine_cellar.apps.wine.models import DrinkRecord

    wine = wine_factory(user=user)
    storage = user.storage_set.first()
    bottle = storage_item_factory(
        wine=wine, storage=storage, user=user, row=2, column=3, deleted=False
    )

    client.force_login(user)
    response = client.post(
        reverse("drink-record-add", kwargs={"pk": wine.pk}),
        {
            "date_consumed": "2024-01-15",
            "storage_item": bottle.pk,
            "rating": 3,
        },
    )

    assert response.status_code == HTTPStatus.FOUND

    # Verify drink record created with bottle reference
    drink_record = DrinkRecord.objects.filter(wine=wine, user=user).first()
    assert drink_record is not None
    assert drink_record.storage_item == bottle

    # Verify bottle marked as deleted
    bottle.refresh_from_db()
    assert bottle.deleted is True

    # Verify stock count decreased
    assert wine.total_stock == 0


@pytest.mark.django_db
def test_drink_record_without_bottle_still_works(client, user, wine_factory):
    """Test recording a drink without bottle selection works normally."""
    from wine_cellar.apps.wine.models import DrinkRecord

    wine = wine_factory(user=user)

    client.force_login(user)
    response = client.post(
        reverse("drink-record-add", kwargs={"pk": wine.pk}),
        {"date_consumed": "2024-01-15", "rating": 2},
    )

    assert response.status_code == HTTPStatus.FOUND
    drink_record = DrinkRecord.objects.filter(wine=wine, user=user).first()
    assert drink_record is not None
    assert drink_record.storage_item is None


@pytest.mark.django_db
def test_wine_detail_record_drink_link_preserves_selected_storage_item(
    client, user, wine_factory, storage_item_factory
):
    wine = wine_factory(user=user)
    storage = user.storage_set.first()
    bottle = storage_item_factory(wine=wine, storage=storage, user=user)
    client.force_login(user)

    response = client.get(
        reverse("wine-detail", kwargs={"pk": wine.pk}),
        {"storage_item": bottle.pk},
    )

    assert response.status_code == HTTPStatus.OK
    expected_drink_url = (
        reverse("drink-record-add", kwargs={"pk": wine.pk})
        + f"?storage_item={bottle.pk}"
    )
    assert f'href="{expected_drink_url}"' in response.content.decode()


@pytest.mark.django_db
def test_form_shows_only_available_bottles(
    client, user, wine_factory, storage_item_factory
):
    """Test form only shows non-deleted bottles for the specific wine."""
    wine = wine_factory(user=user)
    wine2 = wine_factory(user=user)
    storage = user.storage_set.first()

    bottle1 = storage_item_factory(wine=wine, storage=storage, user=user, deleted=False)
    storage_item_factory(
        wine=wine, storage=storage, user=user, deleted=True
    )  # Should be excluded (deleted)
    storage_item_factory(
        wine=wine2, storage=storage, user=user, deleted=False
    )  # Should be excluded (different wine)

    client.force_login(user)
    response = client.get(reverse("drink-record-add", kwargs={"pk": wine.pk}))

    form = response.context["form"]
    available_bottles = list(form.fields["storage_item"].queryset)

    assert len(available_bottles) == 1
    assert bottle1 in available_bottles


@pytest.mark.django_db
def test_cellar_value_uses_wine_price_as_fallback(
    client, user, wine_factory, storage_item_factory
):
    """Cellar value total uses wine.price when storage_item.price is NULL."""
    Wine.objects.filter(user=user).delete()
    storage = user.storage_set.first()
    wine = wine_factory(user=user, country="FR", price=20.00)
    # item has no price; should fall back to wine.price=20
    storage_item_factory(wine=wine, storage=storage, price=None)
    client.force_login(user)
    r = client.get(reverse("cellar-value"))
    assert r.status_code == HTTPStatus.OK
    assert r.context_data["total_value"] == 20


@pytest.mark.django_db
def test_cellar_value_zero_item_price_not_overridden(
    client, user, wine_factory, storage_item_factory
):
    """An explicit item price of zero is respected and not replaced by wine.price."""
    Wine.objects.filter(user=user).delete()
    storage = user.storage_set.first()
    wine = wine_factory(user=user, country="FR", price=20.00)
    # item price explicitly set to 0 — must NOT fall through to wine.price
    storage_item_factory(wine=wine, storage=storage, price=0)
    client.force_login(user)
    r = client.get(reverse("cellar-value"))
    assert r.status_code == HTTPStatus.OK
    assert r.context_data["total_value"] == 0


@pytest.mark.django_db
def test_cellar_value_by_country_uses_wine_price_fallback(
    client, user, wine_factory, storage_item_factory
):
    """Per-country breakdown uses wine.price when storage_item.price is NULL."""
    Wine.objects.filter(user=user).delete()
    storage = user.storage_set.first()
    wine = wine_factory(user=user, country="FR", price=30.00)
    storage_item_factory(wine=wine, storage=storage, price=None)
    client.force_login(user)
    r = client.get(reverse("cellar-value"))
    assert r.status_code == HTTPStatus.OK
    by_group = r.context_data["by_group"]
    assert by_group["France"]["value"] == 30


@pytest.mark.django_db
def test_stats_dashboard_renders(client, user):
    """Stats dashboard page loads successfully for authenticated users."""
    client.force_login(user)
    r = client.get(reverse("stats-dashboard"))
    assert r.status_code == HTTPStatus.OK


@pytest.mark.django_db
def test_stats_dashboard_unauthenticated(client):
    """Unauthenticated users are redirected from the stats dashboard."""
    r = client.get(reverse("stats-dashboard"))
    assert r.status_code == HTTPStatus.FOUND


@pytest.mark.django_db
def test_stats_dashboard_by_type(client, user, wine_factory, storage_item_factory):
    """Stats dashboard shows correct by-type breakdown."""
    Wine.objects.filter(user=user).delete()
    storage = user.storage_set.first()
    wine_factory(user=user, wine_type="RE")  # Red, no storage item
    w = wine_factory(user=user, wine_type="WH")  # White, in stock
    storage_item_factory(wine=w, storage=storage)
    client.force_login(user)
    r = client.get(reverse("stats-dashboard"))
    assert r.status_code == HTTPStatus.OK
    by_type = r.context_data["by_type"]
    assert by_type.get("White", 0) == 1
    assert "Red" not in by_type


@pytest.mark.django_db
def test_stats_dashboard_by_storage(client, user, wine_factory, storage_item_factory):
    """Stats dashboard shows value grouped by storage location."""
    Wine.objects.filter(user=user).delete()
    storage = user.storage_set.first()
    wine = wine_factory(user=user, price=50.00)
    storage_item_factory(wine=wine, storage=storage, price=None)
    client.force_login(user)
    r = client.get(reverse("stats-dashboard"))
    assert r.status_code == HTTPStatus.OK
    by_storage = r.context_data["by_storage"]
    assert storage.name in by_storage
    assert by_storage[storage.name]["value"] == 50


@pytest.mark.django_db
def test_stats_dashboard_purchase_trends(
    client, user, wine_factory, storage_item_factory
):
    """Stats dashboard shows purchase trends over time."""
    storage = user.storage_set.first()
    wine = wine_factory(user=user)
    storage_item_factory(wine=wine, storage=storage)
    client.force_login(user)
    r = client.get(reverse("stats-dashboard"))
    assert r.status_code == HTTPStatus.OK
    by_month = r.context_data["by_month"]
    assert len(by_month) >= 1


@pytest.mark.django_db
def test_stats_dashboard_charts_include_accessible_descriptions(
    client, user, wine_factory, storage_item_factory
):
    Wine.objects.filter(user=user).delete()
    storage = user.storage_set.first()
    wine = wine_factory(user=user, wine_type="WH", country="FR", price=18.00)
    storage_item_factory(wine=wine, storage=storage, price=None)
    client.force_login(user)
    r = client.get(reverse("stats-dashboard"))
    assert r.status_code == HTTPStatus.OK
    content = r.content.decode()
    assert 'id="chartByTypeSummary"' in content
    assert 'aria-describedby="chartByTypeSummary"' in content
    assert 'aria-label="Bottles by country chart"' in content
    assert 'aria-describedby="chartByStorageSummary"' in content


@pytest.mark.django_db
def test_wine_check_duplicate_unauthenticated(client):
    """Unauthenticated requests to the check-duplicate endpoint are redirected."""
    r = client.get(reverse("wine-check-duplicate"), {"name": "Chateau Margaux"})
    assert r.status_code == HTTPStatus.FOUND


@pytest.mark.django_db
def test_wine_check_duplicate_no_matches(client, user):
    """Returns empty list when no similar wines exist."""
    client.force_login(user)
    r = client.get(reverse("wine-check-duplicate"), {"name": "Unique Vintage 2020"})
    assert r.status_code == HTTPStatus.OK
    data = r.json()
    assert data["similar"] == []


@pytest.mark.django_db
def test_wine_check_duplicate_short_name(client, user):
    """Returns empty list when name is too short to check."""
    client.force_login(user)
    r = client.get(reverse("wine-check-duplicate"), {"name": "Ch"})
    assert r.status_code == HTTPStatus.OK
    assert r.json()["similar"] == []


@pytest.mark.django_db
def test_wine_check_duplicate_finds_similar(client, user, wine_factory):
    """Returns existing wine when name closely matches."""
    wine_factory(user=user, name="Chateau Margaux")
    client.force_login(user)
    r = client.get(reverse("wine-check-duplicate"), {"name": "Chateau Margaux"})
    assert r.status_code == HTTPStatus.OK
    data = r.json()
    assert len(data["similar"]) >= 1
    names = [item["name"] for item in data["similar"]]
    assert "Chateau Margaux" in names


@pytest.mark.django_db
def test_wine_check_duplicate_case_insensitive(client, user, wine_factory):
    """Match is case-insensitive."""
    wine_factory(user=user, name="chateau petrus")
    client.force_login(user)
    r = client.get(reverse("wine-check-duplicate"), {"name": "Chateau Petrus"})
    assert r.status_code == HTTPStatus.OK
    data = r.json()
    assert len(data["similar"]) >= 1


@pytest.mark.django_db
def test_wine_check_duplicate_returns_url(client, user, wine_factory):
    """Each similar entry contains a URL."""
    wine = wine_factory(user=user, name="Opus One")
    client.force_login(user)
    r = client.get(reverse("wine-check-duplicate"), {"name": "Opus One"})
    assert r.status_code == HTTPStatus.OK
    data = r.json()
    assert len(data["similar"]) >= 1
    assert f"/wine/{wine.pk}/" in data["similar"][0]["url"]


@pytest.mark.django_db
def test_wine_check_duplicate_no_cross_household(
    client, user, wine_factory, user_factory
):
    """Does not return wines belonging to a different user's household."""
    other_user = user_factory()
    wine_factory(user=other_user, name="Shared Name Wine")
    client.force_login(user)
    r = client.get(reverse("wine-check-duplicate"), {"name": "Shared Name Wine"})
    assert r.status_code == HTTPStatus.OK
    assert r.json()["similar"] == []
