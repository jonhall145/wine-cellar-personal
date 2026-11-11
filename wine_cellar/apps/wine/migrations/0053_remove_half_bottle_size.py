from django.db import migrations, models


def replace_half_bottle_sizes(apps, schema_editor):
    Size = apps.get_model("wine", "Size")
    Wine = apps.get_model("wine", "Wine")

    for half_size in Size.objects.filter(name="HA").iterator():
        standard_size = (
            Size.objects.filter(name="ST", user_id=half_size.user_id)
            .order_by("pk")
            .first()
        )
        if standard_size:
            Wine.objects.filter(size_id=half_size.pk).update(size_id=standard_size.pk)
            half_size.delete()
        else:
            half_size.name = "ST"
            half_size.save(update_fields=["name"])


class Migration(migrations.Migration):
    dependencies = [
        ("wine", "0052_alter_visionextractionlog_model_used"),
    ]

    operations = [
        migrations.RunPython(replace_half_bottle_sizes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="size",
            name="name",
            field=models.CharField(
                choices=[
                    ("PI", "Piccolo (187ml)"),
                    ("DE", "Demi (375ml)"),
                    ("ST", "Standard (750ml)"),
                    ("LI", "Liter (1L)"),
                    ("MA", "Magnum (1.5L)"),
                    ("JE", "Jeroboam (3L)"),
                    ("RE", "Rehoboam (4.5L)"),
                ],
                default="ST",
                max_length=2,
                verbose_name="Size",
            ),
        ),
    ]
