from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("wine", "0040_alter_appellation_unique_together_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="SaleAlert",
        ),
    ]
