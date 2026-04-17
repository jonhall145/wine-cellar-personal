import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertTemplateUsed

from wine_cellar.apps.storage.models import BottleMoveHistory, Storage, StorageItem


@pytest.mark.django_db
class TestStorageGridData:
    def test_returns_json(self, client, user):
        client.force_login(user)
        r = client.get(reverse("storage-grid-data"))
        assert r.status_code == 200
        data = json.loads(r.content)
        assert "storages" in data
        assert "current_storage_id" in data

    def test_includes_storage_items(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user, name="Grid Wine")
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage, row=1, column=1)
        client.force_login(user)
        r = client.get(reverse("storage-grid-data"))
        data = json.loads(r.content)
        storage_data = data["storages"][0]
        assert len(storage_data["items"]) == 1
        assert storage_data["items"][0]["wine"]["name"] == "Grid Wine"

    def test_excludes_deleted_items(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage, row=1, column=1, deleted=True)
        client.force_login(user)
        r = client.get(reverse("storage-grid-data"))
        data = json.loads(r.content)
        assert data["storages"][0]["items"] == []

    def test_with_storage_id_param(self, client, user, storage_factory):
        s2 = storage_factory(user=user)
        client.force_login(user)
        r = client.get(reverse("storage-grid-data"), {"storage_id": s2.pk})
        data = json.loads(r.content)
        assert data["current_storage_id"] == s2.pk


@pytest.mark.django_db
class TestMoveBottle:
    def test_move_to_valid_position(
        self, client, user, wine_factory, storage_item_factory, storage_factory
    ):
        wine = wine_factory(user=user)
        storage = storage_factory(user=user, rows=3, columns=3)
        item = storage_item_factory(
            wine=wine, storage=storage, row=1, column=1, user=user
        )
        client.force_login(user)
        r = client.post(
            reverse("storage-move-bottle"),
            json.dumps(
                {
                    "item_id": item.pk,
                    "target_storage_id": storage.pk,
                    "target_row": 2,
                    "target_column": 3,
                }
            ),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.content)
        assert data["success"] is True
        item.refresh_from_db()
        assert item.row == 2
        assert item.column == 3

    def test_missing_fields(self, client, user):
        client.force_login(user)
        r = client.post(
            reverse("storage-move-bottle"),
            json.dumps({"item_id": 999}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_invalid_json(self, client, user):
        client.force_login(user)
        r = client.post(
            reverse("storage-move-bottle"),
            "bad json",
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_item_not_found(self, client, user, storage_factory):
        storage = storage_factory(user=user, rows=2, columns=2)
        client.force_login(user)
        r = client.post(
            reverse("storage-move-bottle"),
            json.dumps(
                {
                    "item_id": 99999,
                    "target_storage_id": storage.pk,
                    "target_row": 1,
                    "target_column": 1,
                }
            ),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_invalid_row(
        self, client, user, wine_factory, storage_item_factory, storage_factory
    ):
        wine = wine_factory(user=user)
        storage = storage_factory(user=user, rows=2, columns=2)
        item = storage_item_factory(
            wine=wine, storage=storage, row=1, column=1, user=user
        )
        client.force_login(user)
        r = client.post(
            reverse("storage-move-bottle"),
            json.dumps(
                {
                    "item_id": item.pk,
                    "target_storage_id": storage.pk,
                    "target_row": 5,
                    "target_column": 1,
                }
            ),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_occupied_position(
        self, client, user, wine_factory, storage_item_factory, storage_factory
    ):
        storage = storage_factory(user=user, rows=2, columns=2)
        wine1 = wine_factory(user=user)
        wine2 = wine_factory(user=user, name="Second Wine")
        item1 = storage_item_factory(
            wine=wine1, storage=storage, row=1, column=1, user=user
        )
        storage_item_factory(wine=wine2, storage=storage, row=2, column=2, user=user)
        client.force_login(user)
        r = client.post(
            reverse("storage-move-bottle"),
            json.dumps(
                {
                    "item_id": item1.pk,
                    "target_storage_id": storage.pk,
                    "target_row": 2,
                    "target_column": 2,
                }
            ),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_noop_same_position(
        self, client, user, wine_factory, storage_item_factory, storage_factory
    ):
        storage = storage_factory(user=user, rows=2, columns=2)
        wine = wine_factory(user=user)
        item = storage_item_factory(
            wine=wine, storage=storage, row=1, column=1, user=user
        )
        client.force_login(user)
        r = client.post(
            reverse("storage-move-bottle"),
            json.dumps(
                {
                    "item_id": item.pk,
                    "target_storage_id": storage.pk,
                    "target_row": 1,
                    "target_column": 1,
                }
            ),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.content)
        assert data["success"] is True

    def test_move_creates_history(
        self, client, user, wine_factory, storage_item_factory, storage_factory
    ):
        storage = storage_factory(user=user, rows=3, columns=3)
        wine = wine_factory(user=user)
        item = storage_item_factory(
            wine=wine, storage=storage, row=1, column=1, user=user
        )
        client.force_login(user)
        r = client.post(
            reverse("storage-move-bottle"),
            json.dumps(
                {
                    "item_id": item.pk,
                    "target_storage_id": storage.pk,
                    "target_row": 2,
                    "target_column": 3,
                }
            ),
            content_type="application/json",
        )
        assert r.status_code == 200
        history = BottleMoveHistory.objects.filter(storage_item=item)
        assert history.count() == 1
        entry = history.first()
        assert entry.from_row == 1
        assert entry.from_column == 1
        assert entry.to_row == 2
        assert entry.to_column == 3

    def test_noop_does_not_create_history(
        self, client, user, wine_factory, storage_item_factory, storage_factory
    ):
        storage = storage_factory(user=user, rows=2, columns=2)
        wine = wine_factory(user=user)
        item = storage_item_factory(
            wine=wine, storage=storage, row=1, column=1, user=user
        )
        client.force_login(user)
        client.post(
            reverse("storage-move-bottle"),
            json.dumps(
                {
                    "item_id": item.pk,
                    "target_storage_id": storage.pk,
                    "target_row": 1,
                    "target_column": 1,
                }
            ),
            content_type="application/json",
        )
        assert BottleMoveHistory.objects.filter(storage_item=item).count() == 0


@pytest.mark.django_db
class TestStorageMoveUpDown:
    def test_move_up(self, client, user, storage_factory):
        s1 = user.storage_set.first()
        s2 = storage_factory(user=user)
        # Ensure s2 has higher order
        s1.order = 1
        s1.save()
        s2.order = 2
        s2.save()
        client.force_login(user)
        r = client.get(reverse("storage-move-up", kwargs={"pk": s2.pk}))
        assert r.status_code == 302
        s1.refresh_from_db()
        s2.refresh_from_db()
        assert s2.order < s1.order

    def test_move_down(self, client, user, storage_factory):
        s1 = user.storage_set.first()
        s2 = storage_factory(user=user)
        s1.order = 1
        s1.save()
        s2.order = 2
        s2.save()
        client.force_login(user)
        r = client.get(reverse("storage-move-down", kwargs={"pk": s1.pk}))
        assert r.status_code == 302
        s1.refresh_from_db()
        s2.refresh_from_db()
        assert s1.order > s2.order

    def test_move_up_first_noop(self, client, user):
        s1 = user.storage_set.first()
        s1.order = 1
        s1.save()
        original_order = s1.order
        client.force_login(user)
        r = client.get(reverse("storage-move-up", kwargs={"pk": s1.pk}))
        assert r.status_code == 302
        s1.refresh_from_db()
        assert s1.order == original_order


@pytest.mark.django_db
class TestStorageItemHistory:
    def test_renders(self, client, user, wine_factory, storage_item_factory):
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage, deleted=True)
        client.force_login(user)
        r = client.get(reverse("stock-history"))
        assert r.status_code == 200

    def test_orders_removed_bottles_by_removal_date(
        self, client, user, wine_factory, storage_item_factory
    ):
        storage = user.storage_set.first()
        older_consumed = storage_item_factory(
            wine=wine_factory(user=user, name="Older Consumed"),
            storage=storage,
            user=user,
            deleted=True,
            finished_date=timezone.localdate() - timedelta(days=10),
        )
        newest_given = storage_item_factory(
            wine=wine_factory(user=user, name="Newest Given"),
            storage=storage,
            user=user,
            deleted=True,
            removal_reason=StorageItem.RemovalReason.GIVEN,
            recipient="Alex",
            given_date=timezone.localdate() - timedelta(days=1),
        )
        middle_removed = storage_item_factory(
            wine=wine_factory(user=user, name="Middle Removed"),
            storage=storage,
            user=user,
            deleted=True,
            removal_reason=StorageItem.RemovalReason.REMOVED,
            finished_date=timezone.localdate() - timedelta(days=5),
        )
        undated_removed = storage_item_factory(
            wine=wine_factory(user=user, name="Undated Removed"),
            storage=storage,
            user=user,
            deleted=True,
            removal_reason=StorageItem.RemovalReason.REMOVED,
        )
        StorageItem.objects.filter(pk=undated_removed.pk).update(
            created=timezone.now() - timedelta(days=20)
        )
        undated_removed.refresh_from_db()

        client.force_login(user)
        r = client.get(reverse("stock-history"))

        assert r.status_code == 200
        assert list(r.context["storage_items"])[:4] == [
            newest_given,
            middle_removed,
            older_consumed,
            undated_removed,
        ]


# ---------------------------------------------------------------------------
# Storage CRUD views
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStorageCreateView:
    def test_get_renders_form(self, client, user):
        client.force_login(user)
        r = client.get(reverse("storage-add"))
        assert r.status_code == 200

    def test_post_creates_storage(self, client, user):
        client.force_login(user)
        r = client.post(
            reverse("storage-add"),
            {
                "name": "Wine Fridge",
                "location": "Kitchen",
                "description": "Under counter",
                "rows": 3,
                "columns": 4,
            },
        )
        assert r.status_code == 302
        assert Storage.objects.filter(name="Wine Fridge").exists()

    def test_creates_with_zero_rows(self, client, user):
        """Unlimited shelves (rows=0, columns=0) are valid."""
        client.force_login(user)
        r = client.post(
            reverse("storage-add"),
            {
                "name": "Open Shelf",
                "location": "Garage",
                "description": "",
                "rows": 0,
                "columns": 0,
            },
        )
        assert r.status_code == 302
        s = Storage.objects.get(name="Open Shelf")
        assert s.rows == 0
        assert s.columns == 0


@pytest.mark.django_db
class TestStorageUpdateView:
    def test_get_renders_form(self, client, user):
        storage = user.storage_set.first()
        client.force_login(user)
        r = client.get(reverse("storage-edit", kwargs={"pk": storage.pk}))
        assert r.status_code == 200

    def test_post_updates_storage(self, client, user):
        storage = user.storage_set.first()
        client.force_login(user)
        r = client.post(
            reverse("storage-edit", kwargs={"pk": storage.pk}),
            {
                "name": "Renamed Storage",
                "location": "Basement",
                "description": "Updated desc",
                "rows": 5,
                "columns": 5,
            },
        )
        assert r.status_code == 302
        storage.refresh_from_db()
        assert storage.name == "Renamed Storage"
        assert storage.rows == 5

    def test_redirects_to_detail(self, client, user):
        storage = user.storage_set.first()
        client.force_login(user)
        r = client.post(
            reverse("storage-edit", kwargs={"pk": storage.pk}),
            {
                "name": storage.name,
                "location": storage.location or "Loc",
                "description": "",
                "rows": storage.rows,
                "columns": storage.columns,
            },
        )
        assert r.status_code == 302
        assert str(storage.pk) in r.url

    def test_scoped_to_household(self, client, user_factory, storage_factory):
        owner = user_factory()
        other = user_factory()
        storage = storage_factory(user=owner)
        client.force_login(other)
        r = client.get(reverse("storage-edit", kwargs={"pk": storage.pk}))
        assert r.status_code == 404


@pytest.mark.django_db
class TestStorageDeleteView:
    def test_cannot_delete_last_storage(self, client, user):
        """Must have at least one storage."""
        storage = user.storage_set.first()
        assert user.storage_set.count() == 1
        client.force_login(user)
        r = client.post(reverse("storage-delete", kwargs={"pk": storage.pk}))
        # Should fail (form_invalid returns 200 with errors)
        assert r.status_code == 200
        assert Storage.objects.filter(pk=storage.pk).exists()

    def test_can_delete_when_multiple(self, client, user, storage_factory):
        s1 = user.storage_set.first()
        s2 = storage_factory(user=user)
        client.force_login(user)
        r = client.post(reverse("storage-delete", kwargs={"pk": s2.pk}))
        assert r.status_code == 302
        assert not Storage.objects.filter(pk=s2.pk).exists()
        assert Storage.objects.filter(pk=s1.pk).exists()

    def test_scoped_to_household(self, client, user_factory, storage_factory):
        owner = user_factory()
        other = user_factory()
        storage_factory(user=other)  # ensure other user has 2 storages
        storage = storage_factory(user=owner)
        client.force_login(other)
        r = client.post(reverse("storage-delete", kwargs={"pk": storage.pk}))
        assert r.status_code == 404


@pytest.mark.django_db
class TestStorageDetailView:
    def test_renders(self, client, user):
        storage = user.storage_set.first()
        client.force_login(user)
        r = client.get(reverse("storage-detail", kwargs={"pk": storage.pk}))
        assert r.status_code == 200

    def test_shows_wines(self, client, user, wine_factory, storage_item_factory):
        wine = wine_factory(user=user, name="Detail Wine")
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage)
        client.force_login(user)
        r = client.get(reverse("storage-detail", kwargs={"pk": storage.pk}))
        assert r.status_code == 200

    def test_scoped_to_household(self, client, user_factory, storage_factory):
        owner = user_factory()
        other = user_factory()
        storage = storage_factory(user=owner)
        client.force_login(other)
        r = client.get(reverse("storage-detail", kwargs={"pk": storage.pk}))
        assert r.status_code == 404


@pytest.mark.django_db
class TestStorageListView:
    def test_renders(self, client, user):
        client.force_login(user)
        r = client.get(reverse("storage-list"))
        assert r.status_code == 200
        assert "storages" in r.context

    def test_shows_storages(self, client, user, storage_factory):
        storage_factory(user=user, name="Extra Storage")
        client.force_login(user)
        r = client.get(reverse("storage-list"))
        names = [s.name for s in r.context["storages"]]
        assert "Extra Storage" in names


# ---------------------------------------------------------------------------
# Storage item add / edit views
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStorageItemAddView:
    def test_get_renders_form(self, client, user, wine_factory):
        wine = wine_factory(user=user)
        client.force_login(user)
        r = client.get(reverse("stock-add", kwargs={"pk": wine.pk}))
        assert r.status_code == 200
        assertTemplateUsed(r, "stock_add.html")
        assertTemplateUsed(r, "core/stock_add.html")
        assert r.context["wine"].pk == wine.pk
        assert "free_cells_by_storage" in r.context

    def test_post_creates_item(self, client, user, wine_factory, storage_factory):
        wine = wine_factory(user=user)
        storage = storage_factory(user=user, rows=3, columns=3)
        client.force_login(user)
        r = client.post(
            reverse("stock-add", kwargs={"pk": wine.pk}),
            {
                "storage": storage.pk,
                "row": 1,
                "column": 1,
            },
            follow=True,
        )
        assert r.status_code == 200
        assert StorageItem.objects.filter(wine=wine, storage=storage).exists()

    def test_post_with_price(self, client, user, wine_factory, storage_factory):
        wine = wine_factory(user=user)
        storage = storage_factory(user=user, rows=3, columns=3)
        client.force_login(user)
        r = client.post(
            reverse("stock-add", kwargs={"pk": wine.pk}),
            {
                "storage": storage.pk,
                "row": 1,
                "column": 1,
                "price": "29.99",
            },
            follow=True,
        )
        assert r.status_code == 200
        item = StorageItem.objects.filter(wine=wine, storage=storage).first()
        assert item is not None
        assert str(item.price) == "29.99"

    def test_scoped_to_household(self, client, user_factory, wine_factory):
        owner = user_factory()
        other = user_factory()
        wine = wine_factory(user=owner)
        client.force_login(other)
        r = client.get(reverse("stock-add", kwargs={"pk": wine.pk}))
        assert r.status_code == 404

    def test_storage_suggestions_respect_masks_and_used_slots(
        self, client, user, wine_factory, storage_factory, storage_item_factory
    ):
        wine = wine_factory(user=user)
        other_wine = wine_factory(user=user, name="Other Wine")
        storage = storage_factory(
            user=user,
            name="Masked Rack",
            rows=3,
            columns=3,
            cell_mask=[[1, 1], [1, 2]],
        )
        storage_item_factory(wine=wine, storage=storage, row=1, column=1, user=user)
        storage_item_factory(
            wine=other_wine,
            storage=storage,
            row=1,
            column=2,
            user=user,
        )
        storage_item_factory(
            wine=wine,
            storage=storage,
            row=2,
            column=2,
            user=user,
            deleted=True,
        )

        client.force_login(user)
        r = client.get(reverse("stock-add", kwargs={"pk": wine.pk}))

        assert r.status_code == 200
        assert r.context["storage_suggestions"] == [
            {
                "storage_id": storage.pk,
                "storage_name": "Masked Rack",
                "bottle_count": 1,
                "free_slots": 0,
            }
        ]


@pytest.mark.django_db
class TestStorageItemUpdateView:
    def test_get_renders_form(self, client, user, wine_factory, storage_item_factory):
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        item = storage_item_factory(wine=wine, storage=storage, row=1, column=1)
        client.force_login(user)
        r = client.get(reverse("bottle-edit", kwargs={"pk": item.pk}))
        assert r.status_code == 200
        assert r.context["item"].pk == item.pk
        assert r.context["wine"].pk == wine.pk

    def test_post_updates_item(
        self, client, user, wine_factory, storage_item_factory, storage_factory
    ):
        wine = wine_factory(user=user)
        storage = storage_factory(user=user, rows=3, columns=3)
        item = storage_item_factory(wine=wine, storage=storage, row=1, column=1)
        client.force_login(user)
        r = client.post(
            reverse("bottle-edit", kwargs={"pk": item.pk}),
            {
                "storage": storage.pk,
                "row": 2,
                "column": 2,
                "price": "15.00",
                "rating": "",
            },
            follow=True,
        )
        assert r.status_code == 200
        item.refresh_from_db()
        assert item.row == 2
        assert item.column == 2
        assert str(item.price) == "15.00"

    def test_next_list_redirect(
        self, client, user, wine_factory, storage_item_factory, storage_factory
    ):
        wine = wine_factory(user=user)
        storage = storage_factory(user=user, rows=3, columns=3)
        item = storage_item_factory(wine=wine, storage=storage, row=1, column=1)
        client.force_login(user)
        r = client.post(
            reverse("bottle-edit", kwargs={"pk": item.pk}) + "?next=list",
            {
                "storage": storage.pk,
                "row": 1,
                "column": 1,
                "price": "",
                "is_gift": "",
                "gift_from": "",
                "occasion": "",
                "rating": "",
            },
        )
        assert r.status_code == 302
        assert r.url.endswith(reverse("bottle-list"))

    def test_scoped_to_household(
        self, client, user_factory, wine_factory, storage_item_factory
    ):
        owner = user_factory()
        other = user_factory()
        wine = wine_factory(user=owner)
        storage = owner.storage_set.first()
        item = storage_item_factory(wine=wine, storage=storage)
        client.force_login(other)
        r = client.get(reverse("bottle-edit", kwargs={"pk": item.pk}))
        assert r.status_code == 404


@pytest.mark.django_db
class TestStorageItemDeleteView:
    def test_soft_deletes(self, client, user, wine_factory, storage_item_factory):
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        item = storage_item_factory(wine=wine, storage=storage)
        client.force_login(user)
        r = client.post(reverse("stock-delete", kwargs={"pk": item.pk}))
        assert r.status_code == 302
        item.refresh_from_db()
        assert item.deleted is True

    def test_redirect_to_storage(
        self, client, user, wine_factory, storage_item_factory
    ):
        wine = wine_factory(user=user)
        storage = user.storage_set.first()
        item = storage_item_factory(wine=wine, storage=storage)
        client.force_login(user)
        r = client.post(
            reverse("stock-delete", kwargs={"pk": item.pk}) + "?next=storage"
        )
        assert r.status_code == 302
        assert "storage" in r.url


@pytest.mark.django_db
class TestBottleListView:
    def test_renders(self, client, user, wine_factory, storage_item_factory):
        wine = wine_factory(user=user, name="Listed Bottle")
        storage = user.storage_set.first()
        storage_item_factory(wine=wine, storage=storage)
        client.force_login(user)
        r = client.get(reverse("bottle-list"))
        assert r.status_code == 200
        assert "bottles" in r.context
