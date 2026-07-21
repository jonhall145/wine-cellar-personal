"""Tests for core shared views: QR code, random bottle, detail, list, delete, export."""

import json
from decimal import Decimal
from http import HTTPStatus

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from wine_cellar.apps.storage.models import StorageItem
from wine_cellar.apps.wine.models import PriceHistory, Wine, WineType

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


@pytest.mark.django_db
class TestWineImportView:
    def test_import_creates_wine_and_stock(self, client, user, storage_factory):
        storage = storage_factory(
            user=user,
            household=user.user_settings.active_household,
            rows=0,
            columns=0,
            app_type="wine",
        )
        client.force_login(user)

        csv_file = SimpleUploadedFile(
            "wines.csv",
            (
                "name,type,country,stock,price,grapes\n"
                "Imported Riesling,White,DE,2,12.50,Riesling\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        preview = client.post(
            reverse("wine-import"),
            {"action": "upload", "file": csv_file},
        )
        assert preview.status_code == HTTPStatus.OK
        assert "Step 2: Map columns" in preview.content.decode()

        response = client.post(
            reverse("wine-import"),
            {
                "action": "import",
                "default_storage": storage.pk,
                "map_name": "name",
                "map_wine_type": "type",
                "map_country": "country",
                "map_stock_count": "stock",
                "map_price": "price",
                "map_grapes": "grapes",
            },
            follow=True,
        )

        assert response.status_code == HTTPStatus.OK
        wine = Wine.objects.get(name="Imported Riesling")
        assert wine.grapes.filter(name="Riesling").exists()
        assert StorageItem.objects.filter(wine=wine, deleted=False).count() == 2

    def test_import_with_storage_name_mapping(self, client, user, storage_factory):
        """Test that storage name mapping creates stock in correct storage."""
        storage1 = storage_factory(
            user=user,
            household=user.user_settings.active_household,
            name="Cellar A",
            rows=0,
            columns=0,
            app_type="wine",
        )
        storage2 = storage_factory(
            user=user,
            household=user.user_settings.active_household,
            name="Cellar B",
            rows=0,
            columns=0,
            app_type="wine",
        )
        client.force_login(user)

        csv_file = SimpleUploadedFile(
            "wines.csv",
            (
                "name,type,country,storage,stock\n"
                "Wine A,White,FR,Cellar A,1\n"
                "Wine B,Red,IT,Cellar B,1\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        preview = client.post(
            reverse("wine-import"),
            {"action": "upload", "file": csv_file},
        )
        assert preview.status_code == HTTPStatus.OK

        response = client.post(
            reverse("wine-import"),
            {
                "action": "import",
                "map_name": "name",
                "map_wine_type": "type",
                "map_country": "country",
                "map_stock_count": "stock",
                "map_storage_name": "storage",
            },
            follow=True,
        )

        assert response.status_code == HTTPStatus.OK
        wine_a = Wine.objects.get(name="Wine A")
        wine_b = Wine.objects.get(name="Wine B")
        assert (
            StorageItem.objects.filter(
                wine=wine_a,
                storage=storage1,
                deleted=False,
            ).count()
            == 1
        )
        assert (
            StorageItem.objects.filter(
                wine=wine_b,
                storage=storage2,
                deleted=False,
            ).count()
            == 1
        )

    def test_import_with_bottle_price_mapping(self, client, user, storage_factory):
        """Test that bottle price is correctly parsed and stored."""
        from decimal import Decimal

        storage = storage_factory(
            user=user,
            household=user.user_settings.active_household,
            rows=0,
            columns=0,
            app_type="wine",
        )
        client.force_login(user)

        csv_file = SimpleUploadedFile(
            "wines.csv",
            (
                "name,type,country,stock,bottle_price\n"
                "Expensive Wine,Red,FR,2,45.99\n"
                "Cheap Wine,White,PT,1,8.50\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        preview = client.post(
            reverse("wine-import"),
            {"action": "upload", "file": csv_file},
        )
        assert preview.status_code == HTTPStatus.OK

        response = client.post(
            reverse("wine-import"),
            {
                "action": "import",
                "default_storage": storage.pk,
                "map_name": "name",
                "map_wine_type": "type",
                "map_country": "country",
                "map_stock_count": "stock",
                "map_bottle_price": "bottle_price",
            },
            follow=True,
        )

        assert response.status_code == HTTPStatus.OK
        expensive = Wine.objects.get(name="Expensive Wine")
        cheap = Wine.objects.get(name="Cheap Wine")

        expensive_items = StorageItem.objects.filter(wine=expensive, deleted=False)
        cheap_items = StorageItem.objects.filter(wine=cheap, deleted=False)

        assert all(Decimal("45.99") == item.price for item in expensive_items)
        assert all(Decimal("8.50") == item.price for item in cheap_items)


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

    def test_includes_price_tracking_context(
        self, client, user, wine_factory, source_factory
    ):
        household = user.user_settings.active_household
        wine = wine_factory(user=user, name="Tracked Wine", price=Decimal("14.00"))
        source = source_factory(user=user, household=household, name="Merchant")
        PriceHistory.objects.create(
            wine=wine,
            source=source,
            price=Decimal("16.00"),
            user=user,
            household=household,
        )
        PriceHistory.objects.create(
            wine=wine,
            price=Decimal("18.00"),
            user=user,
            household=household,
        )
        client.force_login(user)

        response = client.get(reverse("wine-detail", kwargs={"pk": wine.pk}))

        assert response.status_code == HTTPStatus.OK
        assert response.context["price_history_latest"].price == Decimal("18.00")
        assert len(response.context["price_history_entries"]) == 2
        assert (
            response.context["price_history_form"]
            .fields["source"]
            .queryset.filter(pk=source.pk)
            .exists()
        )

    def test_renders_ai_summary_with_sources(self, client, user, wine_factory):
        wine = wine_factory(user=user, name="Summarised Wine")
        wine.ai_summary = (
            "This is a concentrated red from a well-known producer "
            "with a long ageing window."
        )
        wine.ai_summary_sources = [
            {"title": "Producer profile", "url": "https://example.com/producer"},
            {"title": "Regional guide", "url": "https://example.com/region"},
        ]
        wine.ai_summary_generated_at = timezone.now()
        wine.ai_summary_model = "claude-sonnet-4-6"
        wine.save(
            update_fields=[
                "ai_summary",
                "ai_summary_sources",
                "ai_summary_generated_at",
                "ai_summary_model",
            ]
        )
        client.force_login(user)

        response = client.get(reverse("wine-detail", kwargs={"pk": wine.pk}))
        content = response.content.decode()

        assert response.status_code == HTTPStatus.OK
        assert "<summary>AI Summary</summary>" in content
        assert "Producer profile" in content
        assert 'href="https://example.com/producer"' in content

    def test_detail_view_renders_photo_viewer_controls(
        self, client, user, wine_factory, wine_image_factory, clear_image_folder
    ):
        wine = wine_factory(user=user, name="Photo Wine")
        wine_image_factory(user=user, wine=wine, image_type="LF")
        client.force_login(user)

        response = client.get(reverse("wine-detail", kwargs={"pk": wine.pk}))

        assert response.status_code == HTTPStatus.OK
        content = response.content.decode()
        assert "data-image-viewer-open" in content
        assert 'id="beverage-image-viewer"' in content
        assert "data-image-viewer-zoom-in" in content
        assert "View Photos" in content

    def test_can_add_price_history(self, client, user, wine_factory, source_factory):
        household = user.user_settings.active_household
        wine = wine_factory(user=user, name="Tracked Wine")
        source = source_factory(user=user, household=household, name="Merchant")
        client.force_login(user)

        response = client.post(
            reverse("wine-price-history-add", kwargs={"pk": wine.pk}),
            {"price": "19.50", "source": source.pk},
        )

        assert response.status_code == HTTPStatus.FOUND
        assert (
            response.url
            == reverse("wine-detail", kwargs={"pk": wine.pk}) + "#price-tracking"
        )
        history_entry = PriceHistory.objects.get(wine=wine)
        assert history_entry.price == Decimal("19.50")
        assert history_entry.source == source
        assert history_entry.user == user
        assert history_entry.household == household
        assert source in wine.source.all()

    def test_consumed_bottles_are_hidden_by_default(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        consumed_bottle = storage_item_factory(
            wine=wine,
            storage=storage,
            user=user,
            row=1,
            column=2,
            deleted=True,
            finished_date=timezone.localdate(),
        )
        client.force_login(user)

        r = client.get(reverse("wine-detail", kwargs={"pk": wine.pk}))
        content = r.content.decode()

        assert r.status_code == HTTPStatus.OK
        assert r.context["consumed_bottle_count"] == 1
        assert r.context["show_consumed_bottles"] is False
        assert "Show consumed bottles (1)" in content
        assert (
            reverse("bottle-history", kwargs={"pk": consumed_bottle.pk}) not in content
        )

    def test_consumed_bottles_can_be_shown(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        consumed_bottle = storage_item_factory(
            wine=wine,
            storage=storage,
            user=user,
            row=1,
            column=2,
            deleted=True,
            finished_date=timezone.localdate(),
        )
        client.force_login(user)

        r = client.get(
            f"{reverse('wine-detail', kwargs={'pk': wine.pk})}?show_consumed=1"
        )
        content = r.content.decode()

        assert r.status_code == HTTPStatus.OK
        assert r.context["show_consumed_bottles"] is True
        assert consumed_bottle in list(r.context["consumed_bottles"])
        assert (
            consumed_bottle.finished_date
            == r.context["consumed_bottles"][0].finished_date
        )
        assert "Hide consumed bottles" in content
        assert reverse("bottle-history", kwargs={"pk": consumed_bottle.pk}) in content

    def test_given_bottles_are_shown_separately(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        gifted_bottle = storage_item_factory(
            wine=wine,
            storage=storage,
            user=user,
            row=1,
            column=2,
            deleted=True,
            removal_reason=StorageItem.RemovalReason.GIVEN,
            recipient="Dana",
            given_occasion="Wedding",
            given_date=timezone.localdate(),
        )
        client.force_login(user)

        r = client.get(
            f"{reverse('wine-detail', kwargs={'pk': wine.pk})}?show_consumed=1"
        )
        content = r.content.decode()

        assert r.status_code == HTTPStatus.OK
        assert r.context["gifted_bottle_count"] == 1
        assert gifted_bottle in list(r.context["gifted_bottles"])
        assert "Given Bottles" in content
        assert "Dana" in content

    def test_given_bottles_toggle_links_to_gifted_section(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        storage_item_factory(
            wine=wine,
            storage=storage,
            user=user,
            deleted=True,
            removal_reason=StorageItem.RemovalReason.GIVEN,
            recipient="Dana",
            given_date=timezone.localdate(),
        )
        client.force_login(user)

        r = client.get(reverse("wine-detail", kwargs={"pk": wine.pk}))
        content = r.content.decode()

        assert r.status_code == HTTPStatus.OK
        assert (
            f'href="{reverse("wine-detail", kwargs={"pk": wine.pk})}'
            "?show_consumed=1#gifted-bottles"
        ) in content

    def test_broken_or_lost_bottles_use_broken_or_lost_copy(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        broken_bottle = storage_item_factory(
            wine=wine,
            storage=storage,
            user=user,
            deleted=True,
            removal_reason=StorageItem.RemovalReason.REMOVED,
            finished_date=timezone.localdate(),
        )
        client.force_login(user)

        r = client.get(reverse("wine-detail", kwargs={"pk": wine.pk}))
        content = r.content.decode()

        assert r.status_code == HTTPStatus.OK
        assert r.context["broken_lost_bottle_count"] == 1
        assert r.context["actual_consumed_bottle_count"] == 0
        assert "Show broken or lost bottles (1)" in content
        assert reverse("bottle-history", kwargs={"pk": broken_bottle.pk}) not in content

        r = client.get(
            f"{reverse('wine-detail', kwargs={'pk': wine.pk})}?show_consumed=1"
        )
        content = r.content.decode()

        assert r.status_code == HTTPStatus.OK
        assert broken_bottle in list(r.context["consumed_bottles"])
        assert "Broken or Lost Bottles" in content
        assert "Broken or lost" in content


# ---------------------------------------------------------------------------
# Wine list view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestWineListView:
    def test_returns_200_with_wines(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user, name="Listed Wine")
        storage_item_factory(wine=wine, user=user)
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

    def test_filter_by_wine_type(
        self, client, user, wine_factory, storage_item_factory
    ):
        red = wine_factory(user=user, wine_type=WineType.RED, name="Red One")
        white = wine_factory(user=user, wine_type=WineType.WHITE, name="White One")
        storage_item_factory(wine=red, user=user)
        storage_item_factory(wine=white, user=user)
        client.force_login(user)
        r = client.get(reverse("wine-list") + "?wine_type=RE")
        assert r.status_code == HTTPStatus.OK
        names = [w.name for w in r.context["object_list"]]
        assert "Red One" in names
        assert "White One" not in names

    def test_filter_by_multiple_wine_types(
        self, client, user, wine_factory, storage_item_factory
    ):
        red = wine_factory(user=user, wine_type=WineType.RED, name="Red One")
        white = wine_factory(user=user, wine_type=WineType.WHITE, name="White One")
        rose = wine_factory(user=user, wine_type=WineType.ROSE, name="Rose One")
        storage_item_factory(wine=red, user=user)
        storage_item_factory(wine=white, user=user)
        storage_item_factory(wine=rose, user=user)
        client.force_login(user)
        r = client.get(reverse("wine-list") + "?wine_type=RE&wine_type=WH")
        assert r.status_code == HTTPStatus.OK
        names = [w.name for w in r.context["object_list"]]
        assert "Red One" in names
        assert "White One" in names
        assert "Rose One" not in names

    def test_list_defaults_to_in_stock_and_oldest_first(
        self, client, user, wine_factory, storage_item_factory
    ):
        oldest = wine_factory(user=user, name="Oldest")
        newest = wine_factory(user=user, name="Newest")
        out_of_stock = wine_factory(user=user, name="Out of Stock")
        old_created = timezone.now() - timezone.timedelta(days=30)
        new_created = timezone.now() - timezone.timedelta(days=1)
        Wine.objects.filter(pk=oldest.pk).update(created=old_created)
        Wine.objects.filter(pk=newest.pk).update(created=new_created)

        storage_item_factory(wine=oldest, user=user)
        storage_item_factory(wine=newest, user=user)

        client.force_login(user)
        response = client.get(reverse("wine-list"))

        assert response.status_code == HTTPStatus.OK
        assert response.context["filter"].data["stock"] == "1"
        assert response.context["filter"].data["order"] == "created"
        assert list(response.context["wines"]) == [oldest, newest]
        assert out_of_stock not in response.context["wines"]

    def test_list_ignores_empty_filter_query_params(
        self, client, user, wine_factory, storage_item_factory
    ):
        oldest = wine_factory(user=user, name="Oldest", vintage=1998)
        newest = wine_factory(user=user, name="Newest", vintage=2021)
        storage_item_factory(wine=oldest, user=user)
        storage_item_factory(wine=newest, user=user)

        client.force_login(user)
        response = client.get(
            reverse("wine-list"),
            {
                "search": "",
                "wine_type": "",
                "category": "",
                "vintage": "",
                "order": "vintage",
            },
        )

        assert response.status_code == HTTPStatus.OK
        assert list(response.context["wines"]) == [oldest, newest]
        assert response.context["filter"].data["order"] == "vintage"

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

    def test_get_preselects_storage_item_from_query_param(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        item = storage_item_factory(wine=wine, storage=storage, user=user)
        client.force_login(user)

        r = client.get(
            reverse("drink-record-add", kwargs={"pk": wine.pk}),
            {"storage_item": item.pk},
        )

        assert r.status_code == HTTPStatus.OK
        assert r.context["form"]["storage_item"].value() == item.pk

    def test_get_defaults_date_consumed_to_today(self, client, user, wine_factory):
        wine = wine_factory(user=user)
        client.force_login(user)
        r = client.get(reverse("drink-record-add", kwargs={"pk": wine.pk}))
        value = r.context["form"]["date_consumed"].value()
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        assert value == timezone.localdate().isoformat()

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

    def test_post_with_photo(self, client, user, wine_factory):
        """Test that photos can be uploaded with drink records."""
        from datetime import date
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from wine_cellar.apps.wine.models import DrinkRecord

        wine = wine_factory(user=user)
        client.force_login(user)

        # Create a valid JPEG image
        image = Image.new("RGB", (100, 100), color="red")
        image_io = BytesIO()
        image.save(image_io, format="JPEG")
        image_io.seek(0)
        uploaded_file = SimpleUploadedFile(
            name="test.jpg",
            content=image_io.getvalue(),
            content_type="image/jpeg",
        )

        response = client.post(
            reverse("drink-record-add", kwargs={"pk": wine.pk}),
            {
                "date_consumed": date.today().isoformat(),
                "photo": uploaded_file,
            },
        )

        assert response.status_code == HTTPStatus.FOUND
        record = DrinkRecord.objects.get(wine=wine)
        assert record.photo
        assert "test.jpg" in record.photo.name

    def test_get_renders_photo_field(self, client, user, wine_factory):
        """Test that the photo field is rendered in the form."""
        wine = wine_factory(user=user)
        client.force_login(user)
        response = client.get(reverse("drink-record-add", kwargs={"pk": wine.pk}))
        assert response.status_code == HTTPStatus.OK
        assert "photo" in response.context["form"].fields


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

    def test_post_updates_photo(self, client, user, wine_factory):
        """Test that photos can be updated on drink records."""
        from datetime import date
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

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

        # Create a valid JPEG image
        image = Image.new("RGB", (100, 100), color="blue")
        image_io = BytesIO()
        image.save(image_io, format="JPEG")
        image_io.seek(0)
        uploaded_file = SimpleUploadedFile(
            name="updated.jpg",
            content=image_io.getvalue(),
            content_type="image/jpeg",
        )

        response = client.post(
            reverse("drink-record-edit", kwargs={"pk": record.pk}),
            {
                "date_consumed": date.today().isoformat(),
                "photo": uploaded_file,
            },
        )

        assert response.status_code == HTTPStatus.FOUND
        record.refresh_from_db()
        assert record.photo
        assert "updated.jpg" in record.photo.name


# ---------------------------------------------------------------------------
# Drink record delete view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDrinkRecordDeleteView:
    def test_get_renders_confirmation_page(self, client, user, wine_factory):
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkRecord

        wine = wine_factory(user=user)
        household = user.user_settings.active_household
        record = DrinkRecord.objects.create(
            wine=wine, user=user, household=household, date_consumed=date.today()
        )
        client.force_login(user)

        r = client.get(reverse("drink-record-delete", kwargs={"pk": record.pk}))

        assert r.status_code == HTTPStatus.OK
        assert "Delete Drink Record" in r.content.decode()

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
# Tasting wheel tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTastingWheel:
    def test_drink_record_create_hides_taste_descriptors_by_default(
        self, client, user, wine_factory
    ):
        wine = wine_factory(user=user)
        client.force_login(user)

        response = client.get(reverse("drink-record-add", kwargs={"pk": wine.pk}))
        html = response.content.decode()

        assert response.status_code == HTTPStatus.OK
        assert '<details id="taste-descriptors-toggle">' in html
        assert '<details id="taste-descriptors-toggle" open>' not in html

    def test_drink_record_edit_shows_taste_descriptors_when_present(
        self, client, user, wine_factory
    ):
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkRecord

        wine = wine_factory(user=user)
        household = user.user_settings.active_household
        record = DrinkRecord.objects.create(
            wine=wine,
            user=user,
            household=household,
            date_consumed=date.today(),
            taste_descriptors=["Apple"],
        )
        client.force_login(user)

        response = client.get(reverse("drink-record-edit", kwargs={"pk": record.pk}))

        assert response.status_code == HTTPStatus.OK
        assert (
            '<details id="taste-descriptors-toggle" open>' in response.content.decode()
        )

    def test_drink_record_create_with_taste_descriptors(
        self, client, user, wine_factory
    ):
        """Test that taste descriptors can be saved on drink record creation."""
        import json
        from datetime import date

        wine = wine_factory(user=user)
        client.force_login(user)
        descriptors = ["Apple", "Citrus", "Pepper"]
        r = client.post(
            reverse("drink-record-add", kwargs={"pk": wine.pk}),
            {
                "date_consumed": date.today().isoformat(),
                "tasting_notes": "Great flavors",
                "rating": "3",
                "taste_descriptors": json.dumps(descriptors),
            },
        )
        assert r.status_code == HTTPStatus.FOUND

        from wine_cellar.apps.wine.models import DrinkRecord

        record = DrinkRecord.objects.filter(wine=wine).first()
        assert record is not None
        assert record.taste_descriptors == descriptors

    def test_drink_record_edit_with_taste_descriptors(self, client, user, wine_factory):
        """Test that taste descriptors can be updated on drink record edit."""
        import json
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkRecord

        wine = wine_factory(user=user)
        household = user.user_settings.active_household
        record = DrinkRecord.objects.create(
            wine=wine,
            user=user,
            household=household,
            date_consumed=date.today(),
            taste_descriptors=["Apple"],
        )
        client.force_login(user)
        new_descriptors = ["Citrus", "Floral"]
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

    def test_drink_record_taste_descriptors_default_empty(
        self, client, user, wine_factory
    ):
        """Test that taste descriptors default to empty list."""
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkRecord

        wine = wine_factory(user=user)
        client.force_login(user)
        r = client.post(
            reverse("drink-record-add", kwargs={"pk": wine.pk}),
            {
                "date_consumed": date.today().isoformat(),
                "tasting_notes": "No descriptors",
                "rating": "2",
            },
        )
        assert r.status_code == HTTPStatus.FOUND

        record = DrinkRecord.objects.filter(wine=wine).first()
        assert record is not None
        assert record.taste_descriptors == []


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

    def test_bottle_backed_records_link_to_bottle_history(
        self, client, user, wine_factory, storage_item_factory
    ):
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkRecord

        wine = wine_factory(user=user)
        household = user.user_settings.active_household
        storage = user.storage_set.first()
        bottle = storage_item_factory(
            wine=wine,
            storage=storage,
            user=user,
            row=2,
            column=3,
            deleted=True,
            finished_date=date(2025, 1, 5),
        )
        DrinkRecord.objects.create(
            wine=wine,
            user=user,
            household=household,
            date_consumed=date(2025, 1, 5),
            storage_item=bottle,
        )

        client.force_login(user)
        r = client.get(reverse("drink-history"))
        content = r.content.decode()

        assert r.status_code == HTTPStatus.OK
        assert reverse("bottle-history", kwargs={"pk": bottle.pk}) in content
        assert reverse("wine-detail", kwargs={"pk": wine.pk}) in content
        assert "Row 2, Cell 3" in content


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

    def test_oldest_and_youngest_links_use_sort_only_urls(self, client, user):
        client.force_login(user)
        response = client.get(reverse("homepage"))
        content = response.content.decode()

        assert f'href="{reverse("wine-list")}?order=vintage"' in content
        assert f'href="{reverse("wine-list")}?order=-vintage"' in content
