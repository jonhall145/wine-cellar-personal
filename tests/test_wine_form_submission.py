import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from wine_cellar.apps.storage.models import StorageItem
from wine_cellar.apps.wine.forms import WineForm
from wine_cellar.apps.wine.models import (
    VisionExtractionLog,
    Wine,
    WineBarcode,
    WineImage,
    Wishlist,
)


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


def _test_image_upload(name="front.jpg"):
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), color="red").save(buffer, format="JPEG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


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

    def test_create_from_wishlist_marks_item_purchased(self, client, user):
        client.force_login(user)
        household = user.user_settings.active_household
        wish = Wishlist.objects.create(
            name="Wishlist Wine",
            user=user,
            household=household,
            wine_type="RE",
            country="FR",
        )

        r = client.post(
            reverse("wine-add"),
            _minimal_wine_data(
                name="Wishlist Wine",
                wine_type="RE",
                country="FR",
                wishlist_item=wish.pk,
            ),
            follow=True,
        )

        assert r.status_code == 200
        wish.refresh_from_db()
        assert wish.purchased is True

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

    def test_create_links_extraction_log_and_saves_label_image(
        self, client, user, clear_image_folder
    ):
        client.force_login(user)
        household = user.user_settings.active_household
        log = VisionExtractionLog.objects.create(
            user=user,
            household=household,
            image_count=1,
            raw_response="{}",
            extracted_data={"name": "Test Wine"},
            confidence="high",
            extracted_fields=["name"],
        )
        session = client.session
        session["extraction_result"] = {"extracted_data": {"name": "Test Wine"}}
        session.save()
        image = _test_image_upload()

        r = client.post(
            reverse("wine-add"),
            _minimal_wine_data(image_front_label=image),
            follow=True,
        )

        assert r.status_code == 200
        wine = Wine.objects.get(name="Test Wine")
        log.refresh_from_db()
        assert log.wine == wine
        assert log.was_successful is True
        assert WineImage.objects.filter(wine=wine, image_type="LF").count() == 1

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

    def test_update_replaces_front_label_image(
        self, client, user, wine_factory, wine_image_factory, clear_image_folder
    ):
        wine = wine_factory(user=user)
        existing_image = wine_image_factory(user=user, wine=wine, image_type="LF")
        client.force_login(user)
        replacement_image = _test_image_upload("replacement.jpg")
        data = _minimal_wine_data(
            name=wine.name,
            wine_type=wine.wine_type,
            country=wine.country,
            image_front_label=replacement_image,
        )

        r = client.post(reverse("wine-edit", kwargs={"pk": wine.pk}), data, follow=True)

        assert r.status_code == 200
        front_images = WineImage.objects.filter(wine=wine, image_type="LF")
        assert front_images.count() == 1
        assert front_images.get().pk != existing_image.pk
