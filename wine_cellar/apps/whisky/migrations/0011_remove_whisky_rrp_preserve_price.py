from django.db import migrations


def preserve_rrp_as_price(apps, schema_editor):
    """Where rrp is set and higher than price (or price is null), use rrp as price."""
    Whisky = apps.get_model("whisky", "Whisky")
    for whisky in Whisky.objects.exclude(rrp__isnull=True):
        if whisky.price is None or whisky.rrp > whisky.price:
            whisky.price = whisky.rrp
            whisky.save(update_fields=["price"])


class Migration(migrations.Migration):

    dependencies = [
        ("whisky", "0010_remove_whisky_sale_alert"),
    ]

    operations = [
        migrations.RunPython(preserve_rrp_as_price, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="whisky",
            name="rrp",
        ),
    ]
