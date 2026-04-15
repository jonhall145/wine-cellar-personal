import pytest
from django.urls import reverse

from wine_cellar.apps.storage.models import StorageItem
from wine_cellar.apps.wine.forms import WineForm
from wine_cellar.apps.wine.models import Wine, WineBarcode


def _minimal_wine_data(**overrides):
    """Return the minimum required POST data for wine creation."""
    data = {
        "name": "Test Wine",
        "wine_type": "RE",
        "country": "FR",
        "form_step": 0,
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_wine_form_storage_fields_use_native_select_widgets(user):
    form = WineForm(user=user)

    assert form.fields["row"].widget.attrs["data-native-select"] == "true"
    assert form.fields["column"].widget.attrs["data-native-select"] == "true"


@pytest.mark.django_db
def test_wine_edit_view_storage_fields_use_native_select_widgets(
    client, user, wine_factory
):
    wine = wine_factory(user=user)
    client.force_login(user)
    response = client.get(reverse("wine-edit", kwargs={"pk": wine.pk}))
    form = response.context["form"]

    assert form.fields["row"].widget.attrs["data-native-select"] == "true"
    assert form.fields["column"].widget.attrs["data-native-select"] == "true"


@pytest.mark.django_db
class TestWineCreateView:
    def test_create_minimal(self, client, user):
        """POST with only required fields creates a wine."""
        client.force_login(user)
        r = client.post(reverse("wine-add"), _minimal_wine_data(), follow=True)
        assert r.status_code == 200
        wine = Wine.objects.get(name="Test Wine")
        assert wine.wine_type == "RE"
        assert wine.country == "FR"
        assert wine.user == user

    def test_create_with_optional_fields(self, client, user):
        """POST with optional fields populates them on the wine."""
        client.force_login(user)
        data = _minimal_wine_data(
            vintage=2020,
            abv=13.5,
            size="ST",
            rating=2,
            comment="Lovely nose",
        )
        r = client.post(reverse("wine-add"), data, follow=True)
        assert r.status_code == 200
        wine = Wine.objects.get(name="Test Wine")
        assert wine.vintage == 2020
        assert wine.abv == 13.5
        assert wine.rating == 2
        assert wine.comment == "Lovely nose"

    def test_create_with_storage(self, client, user):
        """POST with storage fields creates a StorageItem."""
        client.force_login(user)
        storage = user.storage_set.first()
        data = _minimal_wine_data(
            storage=storage.pk,
            row=1,
            column=1,
        )
        r = client.post(reverse("wine-add"), data, follow=True)
        assert r.status_code == 200
        wine = Wine.objects.get(name="Test Wine")
        si = StorageItem.objects.get(wine=wine)
        assert si.storage == storage
        assert si.row == 1
        assert si.column == 1

    def test_create_with_barcode(self, client, user):
        """POST with barcode field creates a WineBarcode."""
        client.force_login(user)
        data = _minimal_wine_data(barcode="1234567890123")
        r = client.post(reverse("wine-add"), data, follow=True)
        assert r.status_code == 200
        wine = Wine.objects.get(name="Test Wine")
        bc = WineBarcode.objects.get(wine=wine)
        assert bc.barcode == "1234567890123"
        assert bc.user == user

    def test_missing_name_returns_form_error(self, client, user):
        """POST without required `name` field re-renders the form with errors."""
        client.force_login(user)
        data = _minimal_wine_data(name="")
        r = client.post(reverse("wine-add"), data)
        assert r.status_code == 200
        assert r.context["form"].errors.get("name")
        assert Wine.objects.count() == 0

    def test_missing_wine_type_returns_form_error(self, client, user):
        """POST without required `wine_type` field re-renders the form with errors."""
        client.force_login(user)
        data = _minimal_wine_data(wine_type="")
        r = client.post(reverse("wine-add"), data)
        assert r.status_code == 200
        assert r.context["form"].errors.get("wine_type")
        assert Wine.objects.count() == 0

    def test_missing_country_returns_form_error(self, client, user):
        """POST without required `country` field re-renders the form with errors."""
        client.force_login(user)
        data = _minimal_wine_data(country="")
        r = client.post(reverse("wine-add"), data)
        assert r.status_code == 200
        assert r.context["form"].errors.get("country")
        assert Wine.objects.count() == 0

    def test_create_redirects_to_wine_list(self, client, user):
        """Successful creation redirects to wine-list."""
        client.force_login(user)
        r = client.post(reverse("wine-add"), _minimal_wine_data())
        assert r.status_code == 302
        assert r.url == reverse("wine-list")

    def test_get_renders_form(self, client, user):
        """GET request renders the wine creation form template."""
        client.force_login(user)
        r = client.get(reverse("wine-add"))
        assert r.status_code == 200
        assert "form" in r.context
        assert "wine_create.html" in [t.name for t in r.templates]


@pytest.mark.django_db
class TestWineUpdateView:
    def test_update_name(self, client, user, wine_factory):
        """POST to wine-edit updates the wine name."""
        wine = wine_factory(user=user)
        client.force_login(user)
        data = _minimal_wine_data(
            name="Updated Name",
            wine_type=wine.wine_type,
            country=wine.country,
        )
        r = client.post(reverse("wine-edit", kwargs={"pk": wine.pk}), data, follow=True)
        assert r.status_code == 200
        wine.refresh_from_db()
        assert wine.name == "Updated Name"

    def test_update_wine_type(self, client, user, wine_factory):
        """POST to wine-edit updates the wine type."""
        wine = wine_factory(user=user, wine_type="RE")
        client.force_login(user)
        data = _minimal_wine_data(
            name=wine.name,
            wine_type="WH",
            country=wine.country,
        )
        r = client.post(reverse("wine-edit", kwargs={"pk": wine.pk}), data, follow=True)
        assert r.status_code == 200
        wine.refresh_from_db()
        assert wine.wine_type == "WH"

    def test_get_renders_form_with_existing_data(self, client, user, wine_factory):
        """GET to wine-edit pre-populates the form with existing wine data."""
        wine = wine_factory(user=user, name="Château Margaux", wine_type="RE")
        client.force_login(user)
        r = client.get(reverse("wine-edit", kwargs={"pk": wine.pk}))
        assert r.status_code == 200
        assert "form" in r.context
        form = r.context["form"]
        assert form.initial["name"] == "Château Margaux"
        assert form.initial["wine_type"] == "RE"

    def test_update_redirects_to_detail(self, client, user, wine_factory):
        """Successful update redirects to the wine detail page."""
        wine = wine_factory(user=user)
        client.force_login(user)
        data = _minimal_wine_data(
            name=wine.name,
            wine_type=wine.wine_type,
            country=wine.country,
        )
        r = client.post(reverse("wine-edit", kwargs={"pk": wine.pk}), data)
        assert r.status_code == 302
        assert r.url == reverse("wine-detail", kwargs={"pk": wine.pk})
