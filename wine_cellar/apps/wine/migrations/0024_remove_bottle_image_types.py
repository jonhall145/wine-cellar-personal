"""Remove bottle front/back image types, keeping only label images."""

from django.db import migrations, models


def remove_bottle_images(apps, schema_editor):
    """Delete WineImage records with bottle front/back types."""
    WineImage = apps.get_model("wine", "WineImage")
    # Delete bottle front (FR) and bottle back (BA) images
    deleted_count, _ = WineImage.objects.filter(image_type__in=["FR", "BA"]).delete()
    if deleted_count:
        print(f"  Deleted {deleted_count} bottle front/back images")


def noop(apps, schema_editor):
    """No-op reverse migration - can't restore deleted images."""
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("wine", "0023_add_performance_indexes"),
    ]

    operations = [
        # First delete any existing bottle images
        migrations.RunPython(remove_bottle_images, noop),
        # Then update the choices for image_type field
        migrations.AlterField(
            model_name="wineimage",
            name="image_type",
            field=models.CharField(
                choices=[("LF", "Label Front"), ("LB", "Label Back")],
                default="LF",
                max_length=3,
                verbose_name="Image Type",
            ),
        ),
    ]
