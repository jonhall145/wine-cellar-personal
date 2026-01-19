"""Admin configuration for hardware models."""

from django.contrib import admin

from .models import (
    HardwareDevice,
    OfflineOperation,
)


@admin.register(HardwareDevice)
class HardwareDeviceAdmin(admin.ModelAdmin):
    list_display = ["name", "device_id", "storage", "user", "is_active", "last_seen"]
    list_filter = ["is_active", "user"]
    search_fields = ["name", "device_id"]
    readonly_fields = ["api_token", "last_seen", "created", "modified"]


@admin.register(OfflineOperation)
class OfflineOperationAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "device",
        "operation_type",
        "client_timestamp",
        "synced_at",
        "applied",
    ]
    list_filter = ["applied", "operation_type", "device"]
    readonly_fields = ["synced_at", "created", "modified"]
