"""Models for hardware (Raspberry Pi) integration."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from wine_cellar.apps.core.models import UserContentModel
from wine_cellar.apps.storage.models import Storage
from wine_cellar.apps.wine.models import Wine


class ChangeType(models.TextChoices):
    """Types of position changes."""

    ADDED = "added", _("Bottle Added")
    REMOVED = "removed", _("Bottle Removed")
    RECONCILIATION = "reconciliation", _("Reconciliation Discrepancy")


class ReviewStatus(models.TextChoices):
    """Status of position change reviews."""

    PENDING = "pending", _("Pending Review")
    APPROVED = "approved", _("Approved")
    REJECTED = "rejected", _("Rejected")
    AUTO_APPLIED = "auto_applied", _("Auto-Applied")


class PositionChangeReview(UserContentModel):
    """
    Detected position changes that need user review.

    When the Pi client detects a bottle was added or removed,
    but the position is uncertain, it creates a review request.
    """

    storage = models.ForeignKey(
        Storage,
        on_delete=models.CASCADE,
        related_name="position_reviews",
        verbose_name=_("Storage"),
    )
    wine = models.ForeignKey(
        Wine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="position_reviews",
        verbose_name=_("Wine"),
    )
    row = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Detected Row"),
        help_text=_("Row detected by vision system, -1 if unknown"),
    )
    column = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Detected Column"),
        help_text=_("Column detected by vision system, -1 if unknown"),
    )
    change_type = models.CharField(
        max_length=20,
        choices=ChangeType,
        verbose_name=_("Change Type"),
    )
    confidence = models.FloatField(
        default=0.0,
        verbose_name=_("Detection Confidence"),
        help_text=_("Confidence score from 0.0 to 1.0"),
    )
    image = models.ImageField(
        upload_to="hardware/position_changes/%Y/%m/",
        null=True,
        blank=True,
        verbose_name=_("Snapshot Image"),
    )
    status = models.CharField(
        max_length=20,
        choices=ReviewStatus,
        default=ReviewStatus.PENDING,
        verbose_name=_("Review Status"),
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Reviewed At"),
    )
    final_row = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Confirmed Row"),
    )
    final_column = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Confirmed Column"),
    )
    notes = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Notes"),
    )

    class Meta:
        verbose_name = _("Position Change Review")
        verbose_name_plural = _("Position Change Reviews")
        ordering = ["-created"]

    def __str__(self):
        change = self.get_change_type_display()
        return f"{change} - {self.storage.name} ({self.row}, {self.column})"


class RackSnapshot(UserContentModel):
    """
    Periodic rack snapshot for reconciliation.

    Captured hourly by the Pi client to track rack state over time.
    """

    storage = models.ForeignKey(
        Storage,
        on_delete=models.CASCADE,
        related_name="snapshots",
        verbose_name=_("Storage"),
    )
    image = models.ImageField(
        upload_to="hardware/snapshots/%Y/%m/%d/",
        verbose_name=_("Snapshot Image"),
    )
    grid_state = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Grid State"),
        help_text=_("JSON representation of detected bottle positions"),
    )
    discrepancies = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Discrepancies"),
        help_text=_("Differences between detected and database state"),
    )
    is_reconciled = models.BooleanField(
        default=False,
        verbose_name=_("Reconciled"),
    )

    class Meta:
        verbose_name = _("Rack Snapshot")
        verbose_name_plural = _("Rack Snapshots")
        ordering = ["-created"]

    def __str__(self):
        return f"{self.storage.name} - {self.created.strftime('%Y-%m-%d %H:%M')}"


class HardwareDevice(UserContentModel):
    """
    Registered hardware devices (Raspberry Pis).

    Allows multiple Pi devices to be registered and authenticated.
    """

    name = models.CharField(
        max_length=100,
        verbose_name=_("Device Name"),
    )
    device_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Device ID"),
        help_text=_("Unique identifier for the device"),
    )
    storage = models.ForeignKey(
        Storage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hardware_devices",
        verbose_name=_("Assigned Storage"),
    )
    api_token = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("API Token"),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
    )
    last_seen = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Seen"),
    )
    firmware_version = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Firmware Version"),
    )

    class Meta:
        verbose_name = _("Hardware Device")
        verbose_name_plural = _("Hardware Devices")

    def __str__(self):
        return f"{self.name} ({self.device_id})"


class OfflineOperation(UserContentModel):
    """
    Offline operations synced from hardware devices.

    When a Pi operates offline, it queues operations and syncs
    them when connectivity is restored.
    """

    device = models.ForeignKey(
        HardwareDevice,
        on_delete=models.CASCADE,
        related_name="offline_operations",
        verbose_name=_("Device"),
    )
    operation_type = models.CharField(
        max_length=50,
        verbose_name=_("Operation Type"),
    )
    operation_data = models.JSONField(
        verbose_name=_("Operation Data"),
    )
    client_timestamp = models.DateTimeField(
        verbose_name=_("Client Timestamp"),
        help_text=_("When the operation was performed on the device"),
    )
    synced_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Synced At"),
    )
    applied = models.BooleanField(
        default=False,
        verbose_name=_("Applied"),
    )
    error = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Error"),
    )

    class Meta:
        verbose_name = _("Offline Operation")
        verbose_name_plural = _("Offline Operations")
        ordering = ["client_timestamp"]

    def __str__(self):
        return f"{self.operation_type} from {self.device.name}"


class RackVisionConfig(UserContentModel):
    """
    Configuration for vision-enabled rack detection.

    Stores settings for the Pi camera rack detection system.
    Only one configuration per user (singleton per user).
    """

    storage = models.ForeignKey(
        Storage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vision_config",
        verbose_name=_("Vision-Enabled Storage"),
        help_text=_("The storage rack monitored by the Pi camera"),
    )
    auto_apply_threshold = models.IntegerField(
        default=90,
        verbose_name=_("Auto-Apply Threshold"),
        help_text=_("Confidence threshold (0-100) for auto-applying detections"),
    )
    enable_hourly_snapshots = models.BooleanField(
        default=True,
        verbose_name=_("Enable Hourly Snapshots"),
    )
    enable_daily_reconciliation = models.BooleanField(
        default=True,
        verbose_name=_("Enable Daily Reconciliation"),
    )
    is_calibrated = models.BooleanField(
        default=False,
        verbose_name=_("Calibrated"),
    )
    calibrated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Calibrated At"),
    )
    calibration_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Calibration Data"),
        help_text=_("Corner points and perspective transform data"),
    )

    class Meta:
        verbose_name = _("Rack Vision Configuration")
        verbose_name_plural = _("Rack Vision Configurations")
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                name="unique_vision_config_per_user",
            )
        ]

    def __str__(self):
        storage_name = self.storage.name if self.storage else "Not configured"
        return f"Vision Config - {storage_name}"
