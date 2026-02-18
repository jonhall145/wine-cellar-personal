from http import HTTPStatus

import pytest
from django.urls import reverse
from pytest_django.asserts import assertRedirects, assertTemplateUsed

from wine_cellar.apps.whisky.models import Whisky


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
        "rrp": "",
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
        "rrp": "",
        "rating": "",
    }
    r = client.post(reverse("whisky-add"), data, follow=True)
    assert r.status_code == HTTPStatus.OK
    whisky = Whisky.objects.get(user=user, name="Laphroaig 10")
    assert whisky.distillery == distillery
    assert whisky.age_statement == 10
