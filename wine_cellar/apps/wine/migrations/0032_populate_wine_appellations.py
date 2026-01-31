"""
Data migration to match existing wines' subregion text to Appellation records.
"""

from django.db import migrations


def populate_appellations(apps, schema_editor):
    """Match existing wines' subregion field to appellations by name."""
    Wine = apps.get_model("wine", "Wine")
    Appellation = apps.get_model("wine", "Appellation")

    # Build a lookup dict of appellation names (case-insensitive)
    appellation_lookup = {}
    for appellation in Appellation.objects.all():
        # Store by lowercase name for case-insensitive matching
        appellation_lookup[appellation.name.lower()] = appellation

    # Find wines with subregion but no appellation
    wines_to_update = Wine.objects.filter(
        subregion__isnull=False,
        appellation__isnull=True,
    ).exclude(subregion="")

    updated_count = 0
    for wine in wines_to_update:
        subregion_lower = wine.subregion.strip().lower()
        if subregion_lower in appellation_lookup:
            wine.appellation = appellation_lookup[subregion_lower]
            wine.save(update_fields=["appellation"])
            updated_count += 1

    if updated_count > 0:
        print(f"\n  Matched {updated_count} wines to appellations")


def reverse_populate(apps, schema_editor):
    """Reverse: clear appellation field (subregion text is preserved)."""
    Wine = apps.get_model("wine", "Wine")
    Wine.objects.filter(appellation__isnull=False).update(appellation=None)


class Migration(migrations.Migration):

    dependencies = [
        ("wine", "0031_add_appellation_model"),
    ]

    operations = [
        migrations.RunPython(populate_appellations, reverse_populate),
    ]
