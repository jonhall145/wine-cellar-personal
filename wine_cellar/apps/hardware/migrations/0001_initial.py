# Generated manually for hardware app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('storage', '0006_storageitem_gift_from_storageitem_is_gift_and_more'),
        ('wine', '0021_convert_size_to_named_choices'),
    ]

    operations = [
        migrations.CreateModel(
            name='HardwareDevice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created')),
                ('modified', models.DateTimeField(auto_now=True, verbose_name='Modified')),
                ('name', models.CharField(max_length=100, verbose_name='Device Name')),
                ('device_id', models.CharField(max_length=100, unique=True, verbose_name='Device ID')),
                ('api_token', models.CharField(max_length=100, unique=True, verbose_name='API Token')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
                ('last_seen', models.DateTimeField(blank=True, null=True, verbose_name='Last Seen')),
                ('firmware_version', models.CharField(blank=True, max_length=50, null=True, verbose_name='Firmware Version')),
                ('storage', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='hardware_devices', to='storage.storage', verbose_name='Assigned Storage')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'Hardware Device',
                'verbose_name_plural': 'Hardware Devices',
            },
        ),
        migrations.CreateModel(
            name='RackSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created')),
                ('modified', models.DateTimeField(auto_now=True, verbose_name='Modified')),
                ('image', models.ImageField(upload_to='hardware/snapshots/%Y/%m/%d/', verbose_name='Snapshot Image')),
                ('grid_state', models.JSONField(blank=True, help_text='JSON representation of detected bottle positions', null=True, verbose_name='Grid State')),
                ('discrepancies', models.JSONField(blank=True, help_text='Differences between detected and database state', null=True, verbose_name='Discrepancies')),
                ('is_reconciled', models.BooleanField(default=False, verbose_name='Reconciled')),
                ('storage', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='snapshots', to='storage.storage', verbose_name='Storage')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'Rack Snapshot',
                'verbose_name_plural': 'Rack Snapshots',
                'ordering': ['-created'],
            },
        ),
        migrations.CreateModel(
            name='PositionChangeReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created')),
                ('modified', models.DateTimeField(auto_now=True, verbose_name='Modified')),
                ('row', models.IntegerField(blank=True, help_text='Row detected by vision system, -1 if unknown', null=True, verbose_name='Detected Row')),
                ('column', models.IntegerField(blank=True, help_text='Column detected by vision system, -1 if unknown', null=True, verbose_name='Detected Column')),
                ('change_type', models.CharField(choices=[('added', 'Bottle Added'), ('removed', 'Bottle Removed'), ('reconciliation', 'Reconciliation Discrepancy')], max_length=20, verbose_name='Change Type')),
                ('confidence', models.FloatField(default=0.0, help_text='Confidence score from 0.0 to 1.0', verbose_name='Detection Confidence')),
                ('image', models.ImageField(blank=True, null=True, upload_to='hardware/position_changes/%Y/%m/', verbose_name='Snapshot Image')),
                ('status', models.CharField(choices=[('pending', 'Pending Review'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('auto_applied', 'Auto-Applied')], default='pending', max_length=20, verbose_name='Review Status')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True, verbose_name='Reviewed At')),
                ('final_row', models.IntegerField(blank=True, null=True, verbose_name='Confirmed Row')),
                ('final_column', models.IntegerField(blank=True, null=True, verbose_name='Confirmed Column')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='Notes')),
                ('storage', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='position_reviews', to='storage.storage', verbose_name='Storage')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='User')),
                ('wine', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='position_reviews', to='wine.wine', verbose_name='Wine')),
            ],
            options={
                'verbose_name': 'Position Change Review',
                'verbose_name_plural': 'Position Change Reviews',
                'ordering': ['-created'],
            },
        ),
        migrations.CreateModel(
            name='OfflineOperation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created')),
                ('modified', models.DateTimeField(auto_now=True, verbose_name='Modified')),
                ('operation_type', models.CharField(max_length=50, verbose_name='Operation Type')),
                ('operation_data', models.JSONField(verbose_name='Operation Data')),
                ('client_timestamp', models.DateTimeField(help_text='When the operation was performed on the device', verbose_name='Client Timestamp')),
                ('synced_at', models.DateTimeField(auto_now_add=True, verbose_name='Synced At')),
                ('applied', models.BooleanField(default=False, verbose_name='Applied')),
                ('error', models.TextField(blank=True, null=True, verbose_name='Error')),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='offline_operations', to='hardware.hardwaredevice', verbose_name='Device')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'Offline Operation',
                'verbose_name_plural': 'Offline Operations',
                'ordering': ['client_timestamp'],
            },
        ),
    ]
