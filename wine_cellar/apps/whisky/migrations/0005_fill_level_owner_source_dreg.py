import django.db.models.deletion
from django.db import migrations, models


def migrate_fill_levels(apps, schema_editor):
    """Convert old 6-level fill to new 3-level fill.

    FU → UN (Unopened)
    3Q, HA, 1Q → OP (Opened)
    NE, EM → DR (Dreg, set dreg_date=today)
    """
    from datetime import date

    WhiskyStorageItem = apps.get_model("whisky", "WhiskyStorageItem")
    today = date.today()

    WhiskyStorageItem.objects.filter(fill_level="FU").update(fill_level="UN")
    WhiskyStorageItem.objects.filter(fill_level__in=["3Q", "HA", "1Q"]).update(
        fill_level="OP"
    )
    WhiskyStorageItem.objects.filter(fill_level__in=["NE", "EM"]).update(
        fill_level="DR", dreg_date=today
    )


class Migration(migrations.Migration):

    dependencies = [
        ("whisky", "0004_country_default_scotland"),
    ]

    operations = [
        # Add dreg_date first so data migration can use it
        migrations.AddField(
            model_name="whiskystorageitem",
            name="dreg_date",
            field=models.DateField(
                blank=True, null=True, verbose_name="Date Entered Dreg"
            ),
        ),
        # Add owner to Whisky
        migrations.AddField(
            model_name="whisky",
            name="owner",
            field=models.CharField(
                blank=True, default="", max_length=100, verbose_name="Owner"
            ),
        ),
        # Add source FK to Whisky
        migrations.AddField(
            model_name="whisky",
            name="source",
            field=models.ForeignKey(
                blank=True,
                help_text="Where this whisky was purchased.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="whisky.whiskysource",
                verbose_name="Source",
            ),
        ),
        # Data migration: convert fill levels before changing choices
        migrations.RunPython(migrate_fill_levels, migrations.RunPython.noop),
        # Update fill_level choices and default
        migrations.AlterField(
            model_name="whiskystorageitem",
            name="fill_level",
            field=models.CharField(
                choices=[("UN", "Unopened"), ("OP", "Opened"), ("DR", "Dreg")],
                default="UN",
                max_length=2,
                verbose_name="Fill Level",
            ),
        ),
    ]
