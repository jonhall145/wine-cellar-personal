"""Models for hardware (Raspberry Pi) integration."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from wine_cellar.apps.storage.models import Storage
from wine_cellar.apps.wine.models import UserContentModel


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
