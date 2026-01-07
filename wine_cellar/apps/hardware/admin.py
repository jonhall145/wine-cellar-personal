"""Admin configuration for hardware models."""

from django.contrib import admin

from .models import (
    PositionChangeReview,
    RackSnapshot,
    HardwareDevice,
    OfflineOperation,
)


@admin.register(HardwareDevice)
class HardwareDeviceAdmin(admin.ModelAdmin):
    list_display = ["name", "device_id", "storage", "user", "is_active", "last_seen"]
    list_filter = ["is_active", "user"]
    search_fields = ["name", "device_id"]
    readonly_fields = ["api_token", "last_seen", "created", "modified"]


@admin.register(PositionChangeReview)
class PositionChangeReviewAdmin(admin.ModelAdmin):
    list_display = [
        "id", "storage", "change_type", "row", "column",
        "confidence", "status", "created"
    ]
    list_filter = ["status", "change_type", "storage"]
    search_fields = ["storage__name", "wine__name"]
    readonly_fields = ["created", "modified"]

    fieldsets = (
        (None, {
            "fields": ("user", "storage", "wine", "change_type")
        }),
        ("Detection", {
            "fields": ("row", "column", "confidence", "image")
        }),
        ("Review", {
            "fields": ("status", "final_row", "final_column", "reviewed_at", "notes")
        }),
    )


@admin.register(RackSnapshot)
class RackSnapshotAdmin(admin.ModelAdmin):
    list_display = ["id", "storage", "created", "is_reconciled", "has_discrepancies"]
    list_filter = ["is_reconciled", "storage"]
    readonly_fields = ["created", "modified", "grid_state", "discrepancies"]

    def has_discrepancies(self, obj):
        return bool(obj.discrepancies)
    has_discrepancies.boolean = True


@admin.register(OfflineOperation)
class OfflineOperationAdmin(admin.ModelAdmin):
    list_display = [
        "id", "device", "operation_type",
        "client_timestamp", "synced_at", "applied"
    ]
    list_filter = ["applied", "operation_type", "device"]
    readonly_fields = ["synced_at", "created", "modified"]
