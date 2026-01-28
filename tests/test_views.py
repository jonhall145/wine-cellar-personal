from http import HTTPStatus

import pytest
from django.urls import reverse
from pytest_django.asserts import (
    assertRedirects,
    assertTemplateNotUsed,
    assertTemplateUsed,
)

from wine_cellar.apps.wine.models import Wine


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
    assertTemplateUsed(response=r, template_name="homepage.html")
    assertTemplateNotUsed(response=r, template_name="account/login.html")


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
    assertTemplateUsed(response=r, template_name="homepage.html")
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
    assertTemplateUsed(response=r, template_name="wine_list.html")
    assert Wine.objects.exists()
    wine = Wine.objects.first()
    assert wine.name == data["name"]
    assert wine.wine_type == data["wine_type"]
    assert wine.abv == data["abv"]
    assert wine.size.name == "ST"
    assert wine.vintage == data["vintage"]
    assert wine.barcode == "12345"


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
    assertTemplateUsed(response=r, template_name="wine_list.html")
    assert Wine.objects.exists()
    wine = Wine.objects.first()
    assert wine.name == data["name"]
    assert wine.wine_type == data["wine_type"]
    assert wine.abv == data["abv"]
    assert wine.size.name == "ST"
    assert wine.vintage == data["vintage"]
    assert wine.barcode == "12345"
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
    assertTemplateUsed(response=r, template_name="wine_list.html")
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
    assertTemplateUsed(response=r, template_name="wine_list.html")
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
    assertTemplateUsed(response=r, template_name="wine_list.html")
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
    assertTemplateUsed(response=r, template_name="wine_list.html")
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
    assertTemplateUsed(response=r, template_name="wine_list.html")
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
    assertTemplateUsed(response=r, template_name="wine_list.html")
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
    assertTemplateUsed(response=r, template_name="wine_list.html")
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
def test_wine_scanned_existing(
    client,
    user,
    wine_factory,
):
    wine = wine_factory(user=user, country="DE", barcode="12345")
    client.force_login(user)
    r = client.get(reverse("wine-scan", kwargs={"code": wine.barcode}), follow=True)
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
    wine_factory(user=user, country="DE", barcode="12345")
    client.force_login(user)
    r = client.get(reverse("wine-scan", kwargs={"code": "00000"}), follow=True)
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="scanned_wine.html")


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
    assertTemplateUsed(response=r, template_name="wine_list.html")
    assert set(r.context_data["wines"]) == {
        wine_in_stock,
        wine_not_in_stock,
        wine_was_in_stock,
    }
    r = client.get(reverse("wine-list") + "?stock=1")
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="wine_list.html")
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
    r = client.get(reverse("wine-list") + "?order=-effective_price", follow=True)
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="wine_list.html")
    assert list(r.context_data["wines"]) == [
        wine_in_stock_expensive,
        wine_in_stock_middle,
        wine_was_in_stock,
        wine_not_in_stock,
        wine_in_stock_cheap,
        wine_no_price,
    ]
    r = client.get(reverse("wine-list") + "?order=effective_price", follow=True)
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="wine_list.html")
    assert list(r.context_data["wines"]) == [
        wine_no_price,
        wine_in_stock_cheap,
        wine_not_in_stock,
        wine_was_in_stock,
        wine_in_stock_middle,
        wine_in_stock_expensive,
    ]


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
