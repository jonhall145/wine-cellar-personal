import csv
import io
import json
from datetime import date

import pytest

from wine_cellar.apps.wine.export import (
    EXPORT_FIELDS,
    _wine_to_dict,
    export_wines_csv,
    export_wines_json,
)


@pytest.mark.django_db
class TestExportWinesCsv:
    def test_header_row(self, user, wine_factory, household):
        wine_factory(user=user, household=household)
        response = export_wines_csv(household)
        reader = csv.reader(io.StringIO(response.content.decode()))
        header = next(reader)
        assert header == EXPORT_FIELDS

    def test_data_rows(self, user, wine_factory, household):
        wine_factory(user=user, household=household, name="Test Wine")
        wine_factory(user=user, household=household, name="Another Wine")
        response = export_wines_csv(household)
        reader = csv.reader(io.StringIO(response.content.decode()))
        rows = list(reader)
        # header + 2 data rows
        assert len(rows) == 3

    def test_content_type(self, user, wine_factory, household):
        wine_factory(user=user, household=household)
        response = export_wines_csv(household)
        assert response["Content-Type"] == "text/csv"

    def test_content_disposition(self, user, wine_factory, household):
        wine_factory(user=user, household=household)
        response = export_wines_csv(household)
        today = date.today().isoformat()
        assert (
            response["Content-Disposition"]
            == f'attachment; filename="wines_export_{today}.csv"'
        )


@pytest.mark.django_db
class TestExportWinesJson:
    def test_json_structure(self, user, wine_factory, household):
        wine_factory(user=user, household=household, name="Test Wine")
        response = export_wines_json(household)
        data = json.loads(response.content.decode())
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "Test Wine"

    def test_content_type(self, user, wine_factory, household):
        wine_factory(user=user, household=household)
        response = export_wines_json(household)
        assert response["Content-Type"] == "application/json"


@pytest.mark.django_db
class TestWineToDict:
    def test_all_export_fields_present(self, user, wine_factory, household):
        wine = (
            wine_factory._meta.model.objects.filter(household=household)
            .with_related()
            .with_stock_count()
            .none()
        )
        # Create a wine and query it properly
        w = wine_factory(user=user, household=household)
        wine = (
            wine_factory._meta.model.objects.filter(pk=w.pk)
            .with_related()
            .with_stock_count()
            .first()
        )
        result = _wine_to_dict(wine)
        for field in EXPORT_FIELDS:
            assert field in result, f"Missing field: {field}"

    def test_handles_null_fields(self, user, wine_factory, household):
        w = wine_factory(
            user=user,
            household=household,
            vintage=None,
            abv=None,
            price=None,
            category=None,
        )
        wine = (
            wine_factory._meta.model.objects.filter(pk=w.pk)
            .with_related()
            .with_stock_count()
            .first()
        )
        result = _wine_to_dict(wine)
        assert result["vintage"] == ""
        assert result["abv"] == ""
        assert result["price"] == ""
        assert result["category"] == ""
