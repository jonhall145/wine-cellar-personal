"""Tests for storage template tags."""

import json

from wine_cellar.apps.storage.templatetags.storage_tags import storage_cells


class TestStorageCellsTag:
    def test_renders_div_with_data_attribute(self):
        data = [{"id": 1, "name": "Shelf A"}]
        result = storage_cells(data)
        assert 'id="storage-data"' in result
        assert "data-attributes" in result

    def test_serializes_data_as_json(self):
        data = [{"id": 1, "name": "Shelf A", "rows": 3, "columns": 5}]
        result = storage_cells(data)
        # format_html escapes quotes in the attribute value
        from django.utils.html import escape

        assert escape(json.dumps(data)) in result

    def test_empty_list(self):
        result = storage_cells([])
        assert 'id="storage-data"' in result
        assert "[]" in result

    def test_escapes_html_in_json(self):
        data = [{"name": '<script>alert("xss")</script>'}]
        result = storage_cells(data)
        # Django's format_html should escape the attribute value
        assert "<script>" not in result

    def test_multiple_storages(self):
        data = [
            {"id": 1, "name": "Shelf A"},
            {"id": 2, "name": "Shelf B"},
        ]
        result = storage_cells(data)
        assert 'id="storage-data"' in result
