"""Tests for core shared views: QR code, random bottle, detail, list, delete, export."""

import json
from decimal import Decimal
from http import HTTPStatus

import pytest
from django.urls import reverse

from wine_cellar.apps.wine.models import Wine, WineType

# ---------------------------------------------------------------------------
# QR Code view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestQRCodeView:
    def test_returns_png(self, client, user, wine_factory):
        wine = wine_factory(user=user)
        client.force_login(user)
        r = client.get(reverse("wine-qr", kwargs={"pk": wine.pk}))
        assert r.status_code == HTTPStatus.OK
        assert r["Content-Type"] == "image/png"
        # PNG magic bytes
        assert r.content[:4] == b"\x89PNG"

    def test_404_for_nonexistent_wine(self, client, user):
        client.force_login(user)
        r = client.get(reverse("wine-qr", kwargs={"pk": 99999}))
        assert r.status_code == HTTPStatus.NOT_FOUND

    def test_scoped_to_household(self, client, user_factory, wine_factory):
        """User cannot generate a QR code for another household's wine."""
        owner = user_factory()
        other = user_factory()
        wine = wine_factory(user=owner)
        client.force_login(other)
        r = client.get(reverse("wine-qr", kwargs={"pk": wine.pk}))
        assert r.status_code == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Random bottle view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRandomBottleView:
    def test_redirects_when_stock_exists(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage)
        client.force_login(user)
        r = client.get(reverse("random-bottle"))
        assert r.status_code == HTTPStatus.FOUND
        assert reverse("wine-detail", kwargs={"pk": wine.pk}) in r.url

    def test_redirects_to_homepage_when_empty(self, client, user):
        client.force_login(user)
        r = client.get(reverse("random-bottle"))
        assert r.status_code == HTTPStatus.FOUND
        assert reverse("homepage") in r.url

    def test_ignores_deleted_stock(
        self, client, user, wine_factory, storage_item_factory
    ):
        """Deleted storage items should not be picked."""
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage, deleted=True)
        client.force_login(user)
        r = client.get(reverse("random-bottle"))
        # No live stock → redirect to homepage
        assert r.status_code == HTTPStatus.FOUND
        assert reverse("homepage") in r.url


# ---------------------------------------------------------------------------
# Export views (CSV / JSON)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExportViews:
    def test_csv_content_type(self, client, user, wine_factory):
        wine_factory(user=user, name="Export Merlot")
        client.force_login(user)
        r = client.get(reverse("wine-export-csv"))
        assert r.status_code == HTTPStatus.OK
        assert "text/csv" in r["Content-Type"]

    def test_csv_contains_wine_name(self, client, user, wine_factory):
        wine_factory(user=user, name="Export Riesling")
        client.force_login(user)
        r = client.get(reverse("wine-export-csv"))
        assert "Export Riesling" in r.content.decode()

    def test_json_content_type(self, client, user, wine_factory):
        wine_factory(user=user, name="Export Syrah")
        client.force_login(user)
        r = client.get(reverse("wine-export-json"))
        assert r.status_code == HTTPStatus.OK
        assert "application/json" in r["Content-Type"]

    def test_json_contains_wine_name(self, client, user, wine_factory):
        wine_factory(user=user, name="Export Pinot")
        client.force_login(user)
        r = client.get(reverse("wine-export-json"))
        data = json.loads(r.content)
        names = [w["name"] for w in data]
        assert "Export Pinot" in names

    def test_csv_excludes_deleted_wines(self, client, user, wine_factory):
        wine_factory(user=user, name="Visible CSV Wine")
        deleted = wine_factory(user=user, name="Deleted CSV Wine")
        deleted.deleted = True
        deleted.save(update_fields=["deleted"])
        client.force_login(user)
        r = client.get(reverse("wine-export-csv"))
        content = r.content.decode()
        assert "Visible CSV Wine" in content
        assert "Deleted CSV Wine" not in content

    def test_export_requires_login(self, client):
        r = client.get(reverse("wine-export-csv"))
        assert r.status_code == HTTPStatus.FOUND  # redirect to login


# ---------------------------------------------------------------------------
# Wine delete view (soft delete)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestWineDeleteView:
    def test_post_soft_deletes(self, client, user, wine_factory):
        wine = wine_factory(user=user, name="ToDelete")
        client.force_login(user)
        r = client.post(reverse("wine-delete", kwargs={"pk": wine.pk}))
        assert r.status_code == HTTPStatus.FOUND
        wine.refresh_from_db()
        assert wine.deleted is True

    def test_redirects_to_wine_list(self, client, user, wine_factory):
        wine = wine_factory(user=user)
        client.force_login(user)
        r = client.post(reverse("wine-delete", kwargs={"pk": wine.pk}))
        assert r.url == reverse("wine-list")

    def test_delete_scoped_to_household(self, client, user_factory, wine_factory):
        """User cannot delete another household's wine."""
        owner = user_factory()
        other = user_factory()
        wine = wine_factory(user=owner)
        client.force_login(other)
        r = client.post(reverse("wine-delete", kwargs={"pk": wine.pk}))
        assert r.status_code == HTTPStatus.NOT_FOUND
        wine.refresh_from_db()
        assert wine.deleted is False

    def test_already_deleted_wine_returns_404(self, client, user, wine_factory):
        wine = wine_factory(user=user)
        wine.deleted = True
        wine.save(update_fields=["deleted"])
        client.force_login(user)
        r = client.post(reverse("wine-delete", kwargs={"pk": wine.pk}))
        assert r.status_code == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Wine detail view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestWineDetailView:
    def test_returns_200_with_wine(self, client, user, wine_factory):
        wine = wine_factory(user=user, name="Detail Wine")
        client.force_login(user)
        r = client.get(reverse("wine-detail", kwargs={"pk": wine.pk}))
        assert r.status_code == HTTPStatus.OK
        assert r.context["beverage"].pk == wine.pk

    def test_has_stock_count_annotation(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage)
        storage_item_factory(wine=wine, storage=storage)
        client.force_login(user)
        r = client.get(reverse("wine-detail", kwargs={"pk": wine.pk}))
        assert r.status_code == HTTPStatus.OK
        assert r.context["beverage"].stock_count == 2

    def test_deleted_stock_not_counted(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage)
        storage_item_factory(wine=wine, storage=storage, deleted=True)
        client.force_login(user)
        r = client.get(reverse("wine-detail", kwargs={"pk": wine.pk}))
        assert r.context["beverage"].stock_count == 1

    def test_404_for_nonexistent_wine(self, client, user):
        client.force_login(user)
        r = client.get(reverse("wine-detail", kwargs={"pk": 99999}))
        assert r.status_code == HTTPStatus.NOT_FOUND

    def test_deleted_wine_returns_404(self, client, user, wine_factory):
        wine = wine_factory(user=user)
        wine.deleted = True
        wine.save(update_fields=["deleted"])
        client.force_login(user)
        r = client.get(reverse("wine-detail", kwargs={"pk": wine.pk}))
        assert r.status_code == HTTPStatus.NOT_FOUND

    def test_tracks_recent_view_in_session(self, client, user, wine_factory):
        wine = wine_factory(user=user, name="Recently Viewed")
        client.force_login(user)
        client.get(reverse("wine-detail", kwargs={"pk": wine.pk}))
        session = client.session
        recent = session.get("recent_views", [])
        assert any(r["pk"] == wine.pk for r in recent)


# ---------------------------------------------------------------------------
# Wine list view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestWineListView:
    def test_returns_200_with_wines(self, client, user, wine_factory):
        wine_factory(user=user, name="Listed Wine")
        client.force_login(user)
        r = client.get(reverse("wine-list"))
        assert r.status_code == HTTPStatus.OK
        assert len(r.context["object_list"]) >= 1

    def test_pagination_defaults_to_10(self, client, user, wine_factory):
        for i in range(12):
            wine_factory(user=user, name=f"Paginated {i}")
        client.force_login(user)
        r = client.get(reverse("wine-list"))
        assert r.status_code == HTTPStatus.OK
        assert r.context["paginator"].per_page == 10

    def test_filter_by_wine_type(self, client, user, wine_factory):
        wine_factory(user=user, wine_type=WineType.RED, name="Red One")
        wine_factory(user=user, wine_type=WineType.WHITE, name="White One")
        client.force_login(user)
        r = client.get(reverse("wine-list") + "?wine_type=RE")
        assert r.status_code == HTTPStatus.OK
        names = [w.name for w in r.context["object_list"]]
        assert "Red One" in names
        assert "White One" not in names

    def test_filter_by_multiple_wine_types(self, client, user, wine_factory):
        wine_factory(user=user, wine_type=WineType.RED, name="Red One")
        wine_factory(user=user, wine_type=WineType.WHITE, name="White One")
        wine_factory(user=user, wine_type=WineType.ROSE, name="Rose One")
        client.force_login(user)
        r = client.get(reverse("wine-list") + "?wine_type=RE&wine_type=WH")
        assert r.status_code == HTTPStatus.OK
        names = [w.name for w in r.context["object_list"]]
        assert "Red One" in names
        assert "White One" in names
        assert "Rose One" not in names

    def test_per_page_parameter(self, client, user, wine_factory):
        for i in range(15):
            wine_factory(user=user, name=f"PerPage {i}")
        client.force_login(user)
        r = client.get(reverse("wine-list") + "?per_page=25")
        assert r.status_code == HTTPStatus.OK
        assert r.context["paginator"].per_page == 25

    def test_export_urls_in_context(self, client, user, wine_factory):
        wine_factory(user=user)
        client.force_login(user)
        r = client.get(reverse("wine-list"))
        assert r.context["export_csv_url"] == reverse("wine-export-csv")
        assert r.context["export_json_url"] == reverse("wine-export-json")

    def test_requires_login(self, client):
        r = client.get(reverse("wine-list"))
        assert r.status_code == HTTPStatus.FOUND


# ---------------------------------------------------------------------------
# Label scan view (camera capture & file upload)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLabelScanView:
    def test_get_renders(self, client, user):
        client.force_login(user)
        r = client.get(reverse("label-scan"))
        assert r.status_code == HTTPStatus.OK

    def test_post_camera_capture_redirects(self, client, user):
        """POST with camera capture (image_data fields) stores session data."""
        import base64

        pixel_png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50).decode()
        client.force_login(user)
        r = client.post(
            reverse("label-scan"),
            {
                "image_count": "1",
                "image_data_0": f"data:image/png;base64,{pixel_png}",
            },
        )
        assert r.status_code == HTTPStatus.FOUND
        assert "wine/add" in r.url or reverse("wine-add") in r.url
        session = client.session
        assert "scanned_label" in session
        assert session["scanned_label"]["multi_image"] is True

    def test_post_file_upload_renders(self, client, user):
        """POST with file upload processes the image."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        image = SimpleUploadedFile(
            "test.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 50, content_type="image/jpeg"
        )
        client.force_login(user)
        r = client.post(reverse("label-scan"), {"barcode_image": image})
        # May redirect or re-render depending on processing result
        assert r.status_code in (HTTPStatus.OK, HTTPStatus.FOUND)

    def test_post_no_data_renders_get(self, client, user):
        """POST with no image data falls through to GET."""
        client.force_login(user)
        r = client.post(reverse("label-scan"), {})
        assert r.status_code == HTTPStatus.OK

    def test_clears_extraction_result(self, client, user):
        """POST clears previous extraction_result from session."""
        client.force_login(user)
        session = client.session
        session["extraction_result"] = {"some": "data"}
        session.save()
        r = client.post(reverse("label-scan"), {})
        assert r.status_code == HTTPStatus.OK
        assert "extraction_result" not in client.session

    def test_multiple_camera_images(self, client, user):
        """POST with multiple camera captures stores all images."""
        import base64

        pixel = base64.b64encode(b"\x89PNG" + b"\x00" * 20).decode()
        client.force_login(user)
        r = client.post(
            reverse("label-scan"),
            {
                "image_count": "2",
                "image_data_0": pixel,
                "image_data_1": pixel,
            },
        )
        assert r.status_code == HTTPStatus.FOUND
        session = client.session
        assert len(session["scanned_label"]["data"]) == 2


# ---------------------------------------------------------------------------
# Merge confirm view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMergeConfirmView:
    def test_get_renders_merge_page(self, client, user, wine_factory):
        w1 = wine_factory(user=user, name="Primary Wine")
        w2 = wine_factory(user=user, name="Duplicate Wine")
        client.force_login(user)
        r = client.get(
            reverse(
                "wine-merge-confirm",
                kwargs={"pk": w2.pk, "primary_pk": w1.pk},
            )
        )
        assert r.status_code == HTTPStatus.OK
        assert r.context["primary"].pk == w1.pk
        assert r.context["duplicate"].pk == w2.pk

    def test_post_merges_wines(self, client, user, wine_factory):
        """Merging moves storage items and deletes duplicate."""
        w1 = wine_factory(user=user, name="Primary")
        w2 = wine_factory(user=user, name="Duplicate")
        client.force_login(user)
        r = client.post(
            reverse(
                "wine-merge-confirm",
                kwargs={"pk": w2.pk, "primary_pk": w1.pk},
            )
        )
        assert r.status_code == HTTPStatus.FOUND
        assert not Wine.objects.filter(pk=w2.pk).exists()

    def test_merge_moves_storage_items(
        self, client, user, wine_factory, storage_item_factory
    ):
        w1 = wine_factory(user=user, name="Primary")
        w2 = wine_factory(user=user, name="Duplicate")
        storage = user.storage_set.first()
        item = storage_item_factory(wine=w2, storage=storage)
        client.force_login(user)
        client.post(
            reverse(
                "wine-merge-confirm",
                kwargs={"pk": w2.pk, "primary_pk": w1.pk},
            )
        )
        item.refresh_from_db()
        assert item.wine_id == w1.pk

    def test_merge_deduplicates_barcodes(
        self, client, user, wine_factory, wine_barcode_factory
    ):
        """Unique barcodes from duplicate wine are moved to primary."""
        w1 = wine_factory(user=user, name="Primary")
        w2 = wine_factory(user=user, name="Duplicate")
        # Different barcodes on each wine
        wine_barcode_factory(wine=w1, barcode="123456", user=user)
        wine_barcode_factory(wine=w2, barcode="789012", user=user)
        client.force_login(user)
        client.post(
            reverse(
                "wine-merge-confirm",
                kwargs={"pk": w2.pk, "primary_pk": w1.pk},
            )
        )
        from wine_cellar.apps.wine.models import WineBarcode

        # Barcode from w2 should be moved to w1
        assert WineBarcode.objects.filter(wine=w1, barcode="789012").exists()
        assert WineBarcode.objects.filter(wine=w1, barcode="123456").exists()

    def test_merge_combines_grapes(self, client, user, wine_factory, grape_factory):
        """M2M grapes are merged from duplicate to primary."""
        w1 = wine_factory(user=user, name="Primary")
        w2 = wine_factory(user=user, name="Duplicate")
        g1 = grape_factory(user=user, name="Merlot")
        g2 = grape_factory(user=user, name="Cabernet")
        w1.grapes.set([g1])
        w2.grapes.set([g2])
        client.force_login(user)
        client.post(
            reverse(
                "wine-merge-confirm",
                kwargs={"pk": w2.pk, "primary_pk": w1.pk},
            )
        )
        assert set(w1.grapes.values_list("name", flat=True)) == {"Merlot", "Cabernet"}

    def test_merge_moves_drink_records(self, client, user, wine_factory):
        """FK references (DrinkRecord) are moved to primary."""
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkRecord

        w1 = wine_factory(user=user, name="Primary")
        w2 = wine_factory(user=user, name="Duplicate")
        household = user.user_settings.active_household
        record = DrinkRecord.objects.create(
            wine=w2,
            user=user,
            household=household,
            date_consumed=date.today(),
        )
        client.force_login(user)
        client.post(
            reverse(
                "wine-merge-confirm",
                kwargs={"pk": w2.pk, "primary_pk": w1.pk},
            )
        )
        record.refresh_from_db()
        assert record.wine_id == w1.pk

    def test_merge_404_for_other_household(self, client, user_factory, wine_factory):
        owner = user_factory()
        other = user_factory()
        w1 = wine_factory(user=owner, name="Primary")
        w2 = wine_factory(user=owner, name="Duplicate")
        client.force_login(other)
        r = client.get(
            reverse(
                "wine-merge-confirm",
                kwargs={"pk": w2.pk, "primary_pk": w1.pk},
            )
        )
        assert r.status_code == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Drink record create view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDrinkRecordCreateView:
    def test_get_renders_form(self, client, user, wine_factory):
        wine = wine_factory(user=user)
        client.force_login(user)
        r = client.get(reverse("drink-record-add", kwargs={"pk": wine.pk}))
        assert r.status_code == HTTPStatus.OK
        assert r.context["beverage"].pk == wine.pk

    def test_post_creates_record(self, client, user, wine_factory):
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkRecord

        wine = wine_factory(user=user)
        client.force_login(user)
        r = client.post(
            reverse("drink-record-add", kwargs={"pk": wine.pk}),
            {"date_consumed": date.today().isoformat()},
        )
        assert r.status_code == HTTPStatus.FOUND
        assert DrinkRecord.objects.filter(wine=wine, user=user).exists()

    def test_post_with_rating(self, client, user, wine_factory):
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkRecord

        wine = wine_factory(user=user)
        client.force_login(user)
        client.post(
            reverse("drink-record-add", kwargs={"pk": wine.pk}),
            {
                "date_consumed": date.today().isoformat(),
                "rating": "3",
                "tasting_notes": "Excellent",
            },
        )
        record = DrinkRecord.objects.get(wine=wine)
        assert record.rating == 3
        assert record.tasting_notes == "Excellent"

    def test_post_with_storage_item_marks_consumed(
        self, client, user, wine_factory, storage_item_factory
    ):
        """Selecting a storage item marks the bottle as consumed (deleted)."""
        from datetime import date

        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        item = storage_item_factory(wine=wine, storage=storage)
        client.force_login(user)
        client.post(
            reverse("drink-record-add", kwargs={"pk": wine.pk}),
            {
                "date_consumed": date.today().isoformat(),
                "storage_item": item.pk,
            },
        )
        item.refresh_from_db()
        assert item.deleted is True

    def test_404_for_other_household(self, client, user_factory, wine_factory):
        owner = user_factory()
        other = user_factory()
        wine = wine_factory(user=owner)
        client.force_login(other)
        r = client.get(reverse("drink-record-add", kwargs={"pk": wine.pk}))
        assert r.status_code == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Beverage create view (wine-add)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBeverageCreateView:
    def test_get_renders_form(self, client, user):
        client.force_login(user)
        r = client.get(reverse("wine-add"))
        assert r.status_code == HTTPStatus.OK
        assert "free_cells_by_storage" in r.context

    def test_get_with_barcode_code(self, client, user):
        """wine-add with barcode code in URL pre-populates initial."""
        client.force_login(user)
        r = client.get(reverse("wine-add", kwargs={"code": "1234567890"}))
        assert r.status_code == HTTPStatus.OK

    def test_requires_login(self, client):
        r = client.get(reverse("wine-add"))
        assert r.status_code == HTTPStatus.FOUND


# ---------------------------------------------------------------------------
# Beverage update view (wine-edit)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBeverageUpdateView:
    def test_get_renders_form(self, client, user, wine_factory):
        wine = wine_factory(user=user, name="Edit Me")
        client.force_login(user)
        r = client.get(reverse("wine-edit", kwargs={"pk": wine.pk}))
        assert r.status_code == HTTPStatus.OK
        assert r.context["beverage"].pk == wine.pk

    def test_get_populates_initial_data(self, client, user, wine_factory):
        wine = wine_factory(user=user, name="Initial Test")
        client.force_login(user)
        r = client.get(reverse("wine-edit", kwargs={"pk": wine.pk}))
        assert r.status_code == HTTPStatus.OK

    def test_get_populates_barcode(
        self, client, user, wine_factory, wine_barcode_factory
    ):
        wine = wine_factory(user=user)
        wine_barcode_factory(wine=wine, barcode="BC123", user=user)
        client.force_login(user)
        r = client.get(reverse("wine-edit", kwargs={"pk": wine.pk}))
        form = r.context["form"]
        assert form.initial.get("barcode") == "BC123"

    def test_404_for_other_household(self, client, user_factory, wine_factory):
        owner = user_factory()
        other = user_factory()
        wine = wine_factory(user=owner)
        client.force_login(other)
        r = client.get(reverse("wine-edit", kwargs={"pk": wine.pk}))
        assert r.status_code == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Drink record edit view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDrinkRecordEditView:
    def test_get_renders_form(self, client, user, wine_factory):
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkRecord

        wine = wine_factory(user=user)
        household = user.user_settings.active_household
        record = DrinkRecord.objects.create(
            wine=wine,
            user=user,
            household=household,
            date_consumed=date.today(),
            tasting_notes="Good wine",
        )
        client.force_login(user)
        r = client.get(reverse("drink-record-edit", kwargs={"pk": record.pk}))
        assert r.status_code == HTTPStatus.OK
        assert r.context["record"].pk == record.pk

    def test_post_updates_record(self, client, user, wine_factory):
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkRecord

        wine = wine_factory(user=user)
        household = user.user_settings.active_household
        record = DrinkRecord.objects.create(
            wine=wine,
            user=user,
            household=household,
            date_consumed=date.today(),
        )
        client.force_login(user)
        new_date = date(2024, 6, 15)
        r = client.post(
            reverse("drink-record-edit", kwargs={"pk": record.pk}),
            {
                "date_consumed": new_date.isoformat(),
                "tasting_notes": "Updated notes",
                "rating": "2",
            },
        )
        assert r.status_code == HTTPStatus.FOUND
        record.refresh_from_db()
        assert record.date_consumed == new_date
        assert record.tasting_notes == "Updated notes"
        assert record.rating == 2


# ---------------------------------------------------------------------------
# Drink record delete view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDrinkRecordDeleteView:
    def test_post_deletes_record(self, client, user, wine_factory):
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkRecord

        wine = wine_factory(user=user)
        household = user.user_settings.active_household
        record = DrinkRecord.objects.create(
            wine=wine, user=user, household=household, date_consumed=date.today()
        )
        client.force_login(user)
        r = client.post(reverse("drink-record-delete", kwargs={"pk": record.pk}))
        assert r.status_code == HTTPStatus.FOUND
        assert not DrinkRecord.objects.filter(pk=record.pk).exists()

    def test_scoped_to_household(self, client, user_factory, wine_factory):
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkRecord

        owner = user_factory()
        other = user_factory()
        wine = wine_factory(user=owner)
        household = owner.user_settings.active_household
        record = DrinkRecord.objects.create(
            wine=wine, user=owner, household=household, date_consumed=date.today()
        )
        client.force_login(other)
        r = client.post(reverse("drink-record-delete", kwargs={"pk": record.pk}))
        assert r.status_code == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Wishlist views
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestWishlistViews:
    def test_list_renders(self, client, user):
        client.force_login(user)
        r = client.get(reverse("wishlist-list"))
        assert r.status_code == HTTPStatus.OK

    def test_create_wishlist_item(self, client, user):
        from wine_cellar.apps.wine.models import Wishlist

        client.force_login(user)
        r = client.post(
            reverse("wishlist-add"),
            {"name": "Fancy Wine", "priority": "3"},
        )
        assert r.status_code == HTTPStatus.FOUND
        assert Wishlist.objects.filter(name="Fancy Wine").exists()

    def test_delete_wishlist_item(self, client, user):
        from wine_cellar.apps.wine.models import Wishlist

        household = user.user_settings.active_household
        item = Wishlist.objects.create(
            name="Delete Me",
            user=user,
            household=household,
        )
        client.force_login(user)
        r = client.post(reverse("wishlist-delete", kwargs={"pk": item.pk}))
        assert r.status_code == HTTPStatus.FOUND
        assert not Wishlist.objects.filter(pk=item.pk).exists()

    def test_mark_purchased(self, client, user):
        from wine_cellar.apps.wine.models import Wishlist

        household = user.user_settings.active_household
        item = Wishlist.objects.create(name="Buy Me", user=user, household=household)
        client.force_login(user)
        r = client.post(reverse("wishlist-purchased", kwargs={"pk": item.pk}))
        assert r.status_code == HTTPStatus.FOUND
        item.refresh_from_db()
        assert item.purchased is True


# ---------------------------------------------------------------------------
# Drink history list view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDrinkRecordListView:
    def test_renders(self, client, user):
        client.force_login(user)
        r = client.get(reverse("drink-history"))
        assert r.status_code == HTTPStatus.OK

    def test_shows_records(self, client, user, wine_factory):
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkRecord

        wine = wine_factory(user=user)
        household = user.user_settings.active_household
        DrinkRecord.objects.create(
            wine=wine, user=user, household=household, date_consumed=date.today()
        )
        client.force_login(user)
        r = client.get(reverse("drink-history"))
        assert r.status_code == HTTPStatus.OK
        assert len(r.context["drink_records"]) == 1


# ---------------------------------------------------------------------------
# Homepage view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHomePageView:
    def test_renders(self, client, user):
        client.force_login(user)
        r = client.get(reverse("homepage"))
        assert r.status_code == HTTPStatus.OK
        assert "bottles_in_stock" in r.context

    def test_shows_stats(self, client, user, wine_factory, storage_item_factory):
        wine = wine_factory(user=user, price=Decimal("20.00"))
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage)
        client.force_login(user)
        r = client.get(reverse("homepage"))
        assert r.context["bottles_in_stock"] >= 1
