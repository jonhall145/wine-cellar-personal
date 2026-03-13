import pytest

from wine_cellar.apps.storage.models import StorageItem


@pytest.mark.django_db
class TestStorageCellMask:
    def test_is_cell_active_no_mask(self, storage_factory, user):
        storage = storage_factory(user=user, rows=3, columns=3, cell_mask=None)
        assert storage.is_cell_active(1, 1) is True
        assert storage.is_cell_active(3, 3) is True

    def test_is_cell_active_with_mask(self, storage_factory, user):
        mask = [[1, 1], [1, 2], [2, 1]]
        storage = storage_factory(user=user, rows=3, columns=3, cell_mask=mask)
        assert storage.is_cell_active(1, 1) is True
        assert storage.is_cell_active(1, 2) is True
        assert storage.is_cell_active(2, 2) is False
        assert storage.is_cell_active(3, 3) is False

    def test_active_cells_set_no_mask(self, storage_factory, user):
        storage = storage_factory(user=user, cell_mask=None)
        assert storage._active_cells_set is None

    def test_active_cells_set_with_mask(self, storage_factory, user):
        mask = [[1, 1], [2, 3]]
        storage = storage_factory(user=user, cell_mask=mask)
        assert storage._active_cells_set == {(1, 1), (2, 3)}


@pytest.mark.django_db
class TestStorageSlots:
    def test_total_slots_no_mask(self, storage_factory, user):
        storage = storage_factory(user=user, rows=3, columns=4, cell_mask=None)
        assert storage.total_slots == 12

    def test_total_slots_with_mask(self, storage_factory, user):
        mask = [[1, 1], [1, 2], [2, 1]]
        storage = storage_factory(user=user, rows=3, columns=3, cell_mask=mask)
        assert storage.total_slots == 3

    def test_used_slots_counts_non_deleted(
        self, storage_factory, storage_item_factory, wine_factory, user
    ):
        storage = storage_factory(user=user, rows=3, columns=3)
        wine = wine_factory(user=user)
        storage_item_factory(storage=storage, wine=wine, deleted=False)
        storage_item_factory(storage=storage, wine=wine, deleted=False)
        storage_item_factory(storage=storage, wine=wine, deleted=True)
        assert storage.used_slots == 2

    def test_is_full_true(
        self, storage_factory, storage_item_factory, wine_factory, user
    ):
        storage = storage_factory(user=user, rows=1, columns=1)
        wine = wine_factory(user=user)
        storage_item_factory(storage=storage, wine=wine, row=1, column=1)
        assert storage.is_full is True

    def test_is_full_false(self, storage_factory, user):
        storage = storage_factory(user=user, rows=2, columns=2)
        assert storage.is_full is False

    def test_is_slot_occupied(
        self, storage_factory, storage_item_factory, wine_factory, user
    ):
        storage = storage_factory(user=user, rows=3, columns=3)
        wine = wine_factory(user=user)
        storage_item_factory(storage=storage, wine=wine, row=1, column=1)
        assert storage.is_slot_occupied(1, 1) is True
        assert storage.is_slot_occupied(1, 2) is False

    def test_is_slot_occupied_ignores_deleted(
        self, storage_factory, storage_item_factory, wine_factory, user
    ):
        storage = storage_factory(user=user, rows=3, columns=3)
        wine = wine_factory(user=user)
        storage_item_factory(storage=storage, wine=wine, row=1, column=1, deleted=True)
        assert storage.is_slot_occupied(1, 1) is False


@pytest.mark.django_db
class TestGetWines:
    def test_returns_non_deleted_ordered(
        self, storage_factory, storage_item_factory, wine_factory, user
    ):
        storage = storage_factory(user=user, rows=3, columns=3)
        wine = wine_factory(user=user)
        item2 = storage_item_factory(
            storage=storage, wine=wine, row=2, column=1, deleted=False
        )
        item1 = storage_item_factory(
            storage=storage, wine=wine, row=1, column=1, deleted=False
        )
        storage_item_factory(storage=storage, wine=wine, row=1, column=2, deleted=True)
        result = list(storage.get_wines)
        assert len(result) == 2
        assert result[0] == item1
        assert result[1] == item2


@pytest.mark.django_db
class TestGetFreeCellsByRow:
    def test_empty_storage(self, storage_factory, user):
        storage = storage_factory(user=user, rows=2, columns=2)
        free = storage.get_free_cells_by_row()
        assert free == {1: [1, 2], 2: [1, 2]}

    def test_zero_rows(self, storage_factory, user):
        storage = storage_factory(user=user, rows=0, columns=0)
        assert storage.get_free_cells_by_row() == {}

    def test_with_occupied_cells(
        self, storage_factory, storage_item_factory, wine_factory, user
    ):
        storage = storage_factory(user=user, rows=2, columns=3)
        wine = wine_factory(user=user)
        storage_item_factory(storage=storage, wine=wine, row=1, column=2)
        free = storage.get_free_cells_by_row()
        assert free[1] == [1, 3]
        assert free[2] == [1, 2, 3]

    def test_with_exclude_item(
        self, storage_factory, storage_item_factory, wine_factory, user
    ):
        storage = storage_factory(user=user, rows=1, columns=2)
        wine = wine_factory(user=user)
        item = storage_item_factory(storage=storage, wine=wine, row=1, column=1)
        # Without exclude, column 1 is occupied
        assert storage.get_free_cells_by_row()[1] == [2]
        # With exclude, column 1 is free again
        assert storage.get_free_cells_by_row(exclude_item=item)[1] == [1, 2]

    def test_with_mask(self, storage_factory, user):
        mask = [[1, 1], [1, 3], [2, 2]]
        storage = storage_factory(user=user, rows=2, columns=3, cell_mask=mask)
        free = storage.get_free_cells_by_row()
        assert free[1] == [1, 3]
        assert free[2] == [2]


@pytest.mark.django_db
class TestStorageSave:
    def test_default_flag_unsets_other_defaults(self, storage_factory, user):
        s1 = storage_factory(user=user, is_default=True, app_type="wine")
        s2 = storage_factory(user=user, is_default=True, app_type="wine")
        s1.refresh_from_db()
        assert s1.is_default is False
        assert s2.is_default is True

    def test_non_default_doesnt_affect_others(self, storage_factory, user):
        s1 = storage_factory(user=user, is_default=True, app_type="wine")
        storage_factory(user=user, is_default=False, app_type="wine")
        s1.refresh_from_db()
        assert s1.is_default is True


@pytest.mark.django_db
class TestStorageItemQuerySet:
    def test_in_stock_filters_deleted(
        self, storage_factory, storage_item_factory, wine_factory, user
    ):
        storage = storage_factory(user=user)
        wine = wine_factory(user=user)
        storage_item_factory(storage=storage, wine=wine, deleted=False)
        storage_item_factory(storage=storage, wine=wine, deleted=True)
        assert StorageItem.objects.filter(storage=storage).in_stock().count() == 1
