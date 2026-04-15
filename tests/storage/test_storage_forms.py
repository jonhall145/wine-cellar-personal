import json

import pytest

from wine_cellar.apps.storage.forms import (
    StockAddForm,
    StorageForm,
    StorageItemEditForm,
)


@pytest.mark.django_db
class TestStorageForm:
    def test_valid_storage(self):
        form = StorageForm(
            data={
                "name": "Wine Fridge",
                "location": "Kitchen",
                "rows": 5,
                "columns": 10,
                "cell_mask": "",
            }
        )
        assert form.is_valid(), form.errors

    def test_valid_storage_no_grid(self):
        form = StorageForm(
            data={
                "name": "Box",
                "location": "Garage",
                "rows": 0,
                "columns": 0,
                "cell_mask": "",
            }
        )
        assert form.is_valid(), form.errors

    def test_cell_mask_valid_json(self):
        form = StorageForm(
            data={
                "name": "Rack",
                "location": "Cellar",
                "rows": 3,
                "columns": 3,
                "cell_mask": json.dumps([[1, 1], [2, 2], [3, 3]]),
            }
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["cell_mask"] == [[1, 1], [2, 2], [3, 3]]

    def test_cell_mask_empty_list_becomes_none(self):
        form = StorageForm(
            data={
                "name": "Rack",
                "location": "Cellar",
                "rows": 3,
                "columns": 3,
                "cell_mask": json.dumps([]),
            }
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["cell_mask"] is None

    def test_cell_mask_invalid_json(self):
        form = StorageForm(
            data={
                "name": "Rack",
                "location": "Cellar",
                "rows": 3,
                "columns": 3,
                "cell_mask": "not-json",
            }
        )
        assert not form.is_valid()
        assert "cell_mask" in form.errors

    def test_cell_mask_not_a_list(self):
        form = StorageForm(
            data={
                "name": "Rack",
                "location": "Cellar",
                "rows": 3,
                "columns": 3,
                "cell_mask": json.dumps({"a": 1}),
            }
        )
        assert not form.is_valid()
        assert "cell_mask" in form.errors

    def test_cell_mask_invalid_item_format(self):
        form = StorageForm(
            data={
                "name": "Rack",
                "location": "Cellar",
                "rows": 3,
                "columns": 3,
                "cell_mask": json.dumps([[1, 2], [3]]),
            }
        )
        assert not form.is_valid()
        assert "cell_mask" in form.errors

    def test_cell_mask_non_integer_values(self):
        form = StorageForm(
            data={
                "name": "Rack",
                "location": "Cellar",
                "rows": 3,
                "columns": 3,
                "cell_mask": json.dumps([[1, "a"]]),
            }
        )
        assert not form.is_valid()
        assert "cell_mask" in form.errors

    def test_cell_mask_out_of_bounds(self):
        form = StorageForm(
            data={
                "name": "Rack",
                "location": "Cellar",
                "rows": 2,
                "columns": 2,
                "cell_mask": json.dumps([[3, 1]]),
            }
        )
        assert not form.is_valid()
        assert "cell_mask" in form.errors

    def test_cell_mask_requires_rows_and_columns(self):
        form = StorageForm(
            data={
                "name": "Rack",
                "location": "Cellar",
                "cell_mask": json.dumps([[1, 1]]),
            }
        )
        assert not form.is_valid()
        assert "cell_mask" in form.errors

    def test_cell_mask_requires_nonzero_rows_columns(self):
        form = StorageForm(
            data={
                "name": "Rack",
                "location": "Cellar",
                "rows": 0,
                "columns": 0,
                "cell_mask": json.dumps([[1, 1]]),
            }
        )
        assert not form.is_valid()
        assert "cell_mask" in form.errors


@pytest.mark.django_db
class TestStockAddForm:
    def test_valid_submission_with_grid(self, user, wine_factory, storage_factory):
        storage = storage_factory(user=user, rows=5, columns=10)
        wine_factory(user=user)
        form = StockAddForm(
            data={
                "storage": storage.pk,
                "row": 1,
                "column": 1,
            },
            user=user,
        )
        assert form.is_valid(), form.errors

    def test_valid_submission_no_grid(self, user, storage_factory):
        storage = storage_factory(user=user, rows=0, columns=0)
        form = StockAddForm(
            data={
                "storage": storage.pk,
            },
            user=user,
        )
        assert form.is_valid(), form.errors

    def test_row_and_column_use_native_select_widgets(self, user, storage_factory):
        storage_factory(user=user, rows=5, columns=10)
        form = StockAddForm(user=user)

        assert form.fields["row"].widget.attrs["data-native-select"] == "true"
        assert form.fields["column"].widget.attrs["data-native-select"] == "true"

    def test_missing_row_for_grid_storage(self, user, storage_factory):
        storage = storage_factory(user=user, rows=5, columns=10)
        form = StockAddForm(
            data={
                "storage": storage.pk,
                "column": 1,
            },
            user=user,
        )
        assert not form.is_valid()
        codes = [e.code for e in form.errors.as_data()["__all__"]]
        assert "row_column_required" in codes

    def test_missing_column_for_grid_storage(self, user, storage_factory):
        storage = storage_factory(user=user, rows=5, columns=10)
        form = StockAddForm(
            data={
                "storage": storage.pk,
                "row": 1,
            },
            user=user,
        )
        assert not form.is_valid()
        codes = [e.code for e in form.errors.as_data()["__all__"]]
        assert "row_column_required" in codes

    def test_row_exceeds_storage_rows(self, user, storage_factory):
        storage = storage_factory(user=user, rows=3, columns=3)
        form = StockAddForm(
            data={
                "storage": storage.pk,
                "row": 10,
                "column": 1,
            },
            user=user,
        )
        assert not form.is_valid()
        assert "row" in form.errors

    def test_column_exceeds_storage_columns(self, user, storage_factory):
        storage = storage_factory(user=user, rows=3, columns=3)
        form = StockAddForm(
            data={
                "storage": storage.pk,
                "row": 1,
                "column": 10,
            },
            user=user,
        )
        assert not form.is_valid()
        assert "column" in form.errors

    def test_row_for_storage_with_no_rows(self, user, storage_factory):
        storage = storage_factory(user=user, rows=0, columns=5)
        form = StockAddForm(
            data={
                "storage": storage.pk,
                "row": 1,
                "column": 1,
            },
            user=user,
        )
        assert not form.is_valid()
        assert "row" in form.errors

    def test_column_for_storage_with_no_columns(self, user, storage_factory):
        storage = storage_factory(user=user, rows=5, columns=0)
        form = StockAddForm(
            data={
                "storage": storage.pk,
                "row": 1,
                "column": 1,
            },
            user=user,
        )
        assert not form.is_valid()
        assert "column" in form.errors

    def test_slot_already_occupied(
        self, user, wine_factory, storage_factory, storage_item_factory
    ):
        storage = storage_factory(user=user, rows=5, columns=5)
        wine = wine_factory(user=user)
        storage_item_factory(storage=storage, wine=wine, row=2, column=3)

        form = StockAddForm(
            data={
                "storage": storage.pk,
                "row": 2,
                "column": 3,
            },
            user=user,
        )
        assert not form.is_valid()
        codes = [e.code for e in form.errors.as_data()["__all__"]]
        assert "slot_occupied" in codes

    def test_cell_is_masked(self, user, wine_factory, storage_factory):
        # cell_mask lists the *active* cells; (1,2) is not in the mask → inactive
        storage = storage_factory(
            user=user, rows=3, columns=3, cell_mask=[[1, 1], [2, 2], [3, 3]]
        )
        form = StockAddForm(
            data={
                "storage": storage.pk,
                "row": 1,
                "column": 2,
            },
            user=user,
        )
        assert not form.is_valid()
        codes = [e.code for e in form.errors.as_data()["__all__"]]
        assert "cell_inactive" in codes

    def test_cell_active_with_mask(self, user, storage_factory):
        storage = storage_factory(
            user=user, rows=3, columns=3, cell_mask=[[1, 1], [2, 2], [3, 3]]
        )
        form = StockAddForm(
            data={
                "storage": storage.pk,
                "row": 2,
                "column": 2,
            },
            user=user,
        )
        assert form.is_valid(), form.errors


@pytest.mark.django_db
class TestStorageItemEditForm:
    def test_row_and_column_use_native_select_widgets(
        self, user, wine_factory, storage_factory, storage_item_factory
    ):
        storage = storage_factory(user=user, rows=5, columns=5)
        wine = wine_factory(user=user)
        item = storage_item_factory(storage=storage, wine=wine, row=2, column=3)

        form = StorageItemEditForm(user=user, instance=item)

        assert form.fields["row"].widget.attrs["data-native-select"] == "true"
        assert form.fields["column"].widget.attrs["data-native-select"] == "true"

    def test_can_stay_in_same_position(
        self, user, wine_factory, storage_factory, storage_item_factory
    ):
        """Editing an item and keeping it at the same slot should not raise occupied."""
        storage = storage_factory(user=user, rows=5, columns=5)
        wine = wine_factory(user=user)
        item = storage_item_factory(storage=storage, wine=wine, row=2, column=3)

        form = StorageItemEditForm(
            data={
                "storage": storage.pk,
                "row": 2,
                "column": 3,
            },
            user=user,
            instance=item,
        )
        assert form.is_valid(), form.errors

    def test_cannot_move_to_occupied_position(
        self, user, wine_factory, storage_factory, storage_item_factory
    ):
        storage = storage_factory(user=user, rows=5, columns=5)
        wine1 = wine_factory(user=user)
        wine2 = wine_factory(user=user)
        storage_item_factory(storage=storage, wine=wine1, row=1, column=1)
        item2 = storage_item_factory(storage=storage, wine=wine2, row=2, column=2)

        form = StorageItemEditForm(
            data={
                "storage": storage.pk,
                "row": 1,
                "column": 1,
            },
            user=user,
            instance=item2,
        )
        assert not form.is_valid()
        codes = [e.code for e in form.errors.as_data()["__all__"]]
        assert "slot_occupied" in codes

    def test_can_move_to_free_position(
        self, user, wine_factory, storage_factory, storage_item_factory
    ):
        storage = storage_factory(user=user, rows=5, columns=5)
        wine = wine_factory(user=user)
        item = storage_item_factory(storage=storage, wine=wine, row=1, column=1)

        form = StorageItemEditForm(
            data={
                "storage": storage.pk,
                "row": 3,
                "column": 4,
            },
            user=user,
            instance=item,
        )
        assert form.is_valid(), form.errors

    def test_missing_row_for_grid_storage(
        self, user, wine_factory, storage_factory, storage_item_factory
    ):
        storage = storage_factory(user=user, rows=5, columns=5)
        wine = wine_factory(user=user)
        item = storage_item_factory(storage=storage, wine=wine, row=1, column=1)

        form = StorageItemEditForm(
            data={
                "storage": storage.pk,
                "column": 2,
            },
            user=user,
            instance=item,
        )
        assert not form.is_valid()
        codes = [e.code for e in form.errors.as_data()["__all__"]]
        assert "row_column_required" in codes

    def test_row_exceeds_storage(
        self, user, wine_factory, storage_factory, storage_item_factory
    ):
        storage = storage_factory(user=user, rows=3, columns=3)
        wine = wine_factory(user=user)
        item = storage_item_factory(storage=storage, wine=wine, row=1, column=1)

        form = StorageItemEditForm(
            data={
                "storage": storage.pk,
                "row": 10,
                "column": 1,
            },
            user=user,
            instance=item,
        )
        assert not form.is_valid()
        assert "row" in form.errors

    def test_cell_inactive_with_mask(
        self, user, wine_factory, storage_factory, storage_item_factory
    ):
        storage = storage_factory(
            user=user, rows=3, columns=3, cell_mask=[[1, 1], [2, 2]]
        )
        wine = wine_factory(user=user)
        item = storage_item_factory(storage=storage, wine=wine, row=1, column=1)

        form = StorageItemEditForm(
            data={
                "storage": storage.pk,
                "row": 1,
                "column": 2,
            },
            user=user,
            instance=item,
        )
        assert not form.is_valid()
        codes = [e.code for e in form.errors.as_data()["__all__"]]
        assert "cell_inactive" in codes

    def test_without_instance_detects_occupation(
        self, user, wine_factory, storage_factory, storage_item_factory
    ):
        """Without instance, edit form behaves like add form for occupation check."""
        storage = storage_factory(user=user, rows=5, columns=5)
        wine = wine_factory(user=user)
        storage_item_factory(storage=storage, wine=wine, row=1, column=1)

        form = StorageItemEditForm(
            data={
                "storage": storage.pk,
                "row": 1,
                "column": 1,
            },
            user=user,
            instance=None,
        )
        assert not form.is_valid()
        codes = [e.code for e in form.errors.as_data()["__all__"]]
        assert "slot_occupied" in codes
