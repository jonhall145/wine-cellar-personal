"""Data migration: copy Wine.barcode values to WineBarcode rows."""

from django.db import migrations


def copy_barcodes_forward(apps, schema_editor):
    Wine = apps.get_model("wine", "Wine")
    WineBarcode = apps.get_model("wine", "WineBarcode")
    rows = []
    for wine in Wine.objects.filter(barcode__isnull=False).exclude(barcode=""):
        rows.append(
            WineBarcode(
                wine=wine,
                barcode=wine.barcode,
                user_id=wine.user_id,
                household_id=wine.household_id,
            )
        )
    if rows:
        WineBarcode.objects.bulk_create(rows, ignore_conflicts=True)


def copy_barcodes_reverse(apps, schema_editor):
    Wine = apps.get_model("wine", "Wine")
    WineBarcode = apps.get_model("wine", "WineBarcode")
    for wb in WineBarcode.objects.all():
        Wine.objects.filter(pk=wb.wine_id).update(barcode=wb.barcode)


class Migration(migrations.Migration):

    dependencies = [
        ("wine", "0036_create_winebarcode"),
    ]

    operations = [
        migrations.RunPython(copy_barcodes_forward, copy_barcodes_reverse),
    ]
