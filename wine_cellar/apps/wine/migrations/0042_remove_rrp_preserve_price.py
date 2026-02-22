from django.db import migrations


def preserve_rrp_as_price(apps, schema_editor):
    """Where rrp is set and higher than price (or price is null), use rrp as price."""
    Wine = apps.get_model("wine", "Wine")
    for wine in Wine.objects.exclude(rrp__isnull=True):
        if wine.price is None or wine.rrp > wine.price:
            wine.price = wine.rrp
            wine.save(update_fields=["price"])


class Migration(migrations.Migration):

    dependencies = [
        ("wine", "0041_remove_sale_alert"),
    ]

    operations = [
        migrations.RunPython(preserve_rrp_as_price, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="wine",
            name="rrp",
        ),
    ]
