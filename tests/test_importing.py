from django.core.files.uploadedfile import SimpleUploadedFile

from wine_cellar.apps.core.importing import parse_import_excel


class FakeWorksheet:
    max_row = 2

    def iter_rows(self, values_only=True):
        yield ("name", "type", "country")
        yield ("Wine A", "Red")


class FakeWorkbook:
    sheetnames = ["Sheet1"]
    active = FakeWorksheet()


def test_parse_import_excel_handles_short_rows(monkeypatch):
    uploaded_file = SimpleUploadedFile("wines.xlsx", b"stub")

    monkeypatch.setattr(
        "wine_cellar.apps.core.importing.load_workbook",
        lambda *args, **kwargs: FakeWorkbook(),
    )

    headers, rows = parse_import_excel(uploaded_file)

    assert headers == ["name", "type", "country"]
    assert rows == [{"name": "Wine A", "type": "Red", "country": ""}]
