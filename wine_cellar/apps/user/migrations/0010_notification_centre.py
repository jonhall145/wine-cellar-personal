import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("household", "0003_remove_householdsettings_language"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("user", "0009_remove_usersettings_language"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersettings",
            name="drink_window_notifications",
            field=models.CharField(
                choices=[
                    ("NO", "None"),
                    ("EM", "Email only"),
                    ("IA", "In-app only"),
                    ("BO", "Email and in-app"),
                ],
                default="BO",
                help_text="Choose how drink window reminders are delivered.",
                max_length=2,
                verbose_name="Drink Window Delivery",
            ),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="household_invitation_notifications",
            field=models.CharField(
                choices=[
                    ("NO", "None"),
                    ("EM", "Email only"),
                    ("IA", "In-app only"),
                    ("BO", "Email and in-app"),
                ],
                default="IA",
                help_text="Choose how household invitations are delivered.",
                max_length=2,
                verbose_name="Household Invitation Delivery",
            ),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="low_stock_notifications",
            field=models.CharField(
                choices=[
                    ("NO", "None"),
                    ("EM", "Email only"),
                    ("IA", "In-app only"),
                    ("BO", "Email and in-app"),
                ],
                default="IA",
                help_text="Choose how low stock reminders are delivered.",
                max_length=2,
                verbose_name="Low Stock Delivery",
            ),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="price_alert_notifications",
            field=models.CharField(
                choices=[
                    ("NO", "None"),
                    ("EM", "Email only"),
                    ("IA", "In-app only"),
                    ("BO", "Email and in-app"),
                ],
                default="NO",
                help_text="Choose how future price alerts are delivered.",
                max_length=2,
                verbose_name="Price Alert Delivery",
            ),
        ),
        migrations.AlterField(
            model_name="usersettings",
            name="notifications",
            field=models.BooleanField(
                default=True,
                help_text="Global switch for all notification channels.",
                verbose_name="Notifications",
            ),
        ),
        migrations.CreateModel(
            name="InAppNotificationStatus",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created",
                    models.DateTimeField(
                        auto_now_add=True,
                        db_index=True,
                        verbose_name="Created",
                    ),
                ),
                (
                    "modified",
                    models.DateTimeField(auto_now=True, verbose_name="Modified"),
                ),
                (
                    "notification_key",
                    models.CharField(max_length=120, verbose_name="Notification Key"),
                ),
                (
                    "notification_type",
                    models.CharField(max_length=40, verbose_name="Notification Type"),
                ),
                ("is_read", models.BooleanField(default=False, verbose_name="Read")),
                (
                    "read_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="Read At",
                    ),
                ),
                (
                    "dismissed_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="Dismissed At",
                    ),
                ),
                (
                    "household",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(class)s_items",
                        to="household.household",
                        verbose_name="Household",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="User",
                    ),
                ),
            ],
            options={
                "verbose_name": "In-App Notification Status",
                "verbose_name_plural": "In-App Notification Statuses",
                "indexes": [
                    models.Index(
                        fields=["user", "notification_type"],
                        name="notif_status_user_type_idx",
                    )
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="inappnotificationstatus",
            constraint=models.UniqueConstraint(
                fields=("user", "notification_key"),
                name="unique_in_app_notification_status",
            ),
        ),
    ]
