from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("whisky", "0009_alter_caskhistory_unique_together_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="WhiskySaleAlert",
        ),
    ]
