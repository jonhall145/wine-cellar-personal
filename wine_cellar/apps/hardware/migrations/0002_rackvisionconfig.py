# Generated manually for RackVisionConfig model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('storage', '0006_storageitem_gift_from_storageitem_is_gift_and_more'),
        ('hardware', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RackVisionConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created')),
                ('modified', models.DateTimeField(auto_now=True, verbose_name='Modified')),
                ('auto_apply_threshold', models.IntegerField(default=90, help_text='Confidence threshold (0-100) for auto-applying detections', verbose_name='Auto-Apply Threshold')),
                ('enable_hourly_snapshots', models.BooleanField(default=True, verbose_name='Enable Hourly Snapshots')),
                ('enable_daily_reconciliation', models.BooleanField(default=True, verbose_name='Enable Daily Reconciliation')),
                ('is_calibrated', models.BooleanField(default=False, verbose_name='Calibrated')),
                ('calibrated_at', models.DateTimeField(blank=True, null=True, verbose_name='Calibrated At')),
                ('calibration_data', models.JSONField(blank=True, help_text='Corner points and perspective transform data', null=True, verbose_name='Calibration Data')),
                ('storage', models.ForeignKey(blank=True, help_text='The storage rack monitored by the Pi camera', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vision_config', to='storage.storage', verbose_name='Vision-Enabled Storage')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'Rack Vision Configuration',
                'verbose_name_plural': 'Rack Vision Configurations',
            },
        ),
        migrations.AddConstraint(
            model_name='rackvisionconfig',
            constraint=models.UniqueConstraint(fields=('user',), name='unique_vision_config_per_user'),
        ),
    ]
