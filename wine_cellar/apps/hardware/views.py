"""API views for hardware (Raspberry Pi) integration."""

import json
import secrets
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_not_required, login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView

from wine_cellar.apps.storage.models import Storage, StorageItem
from wine_cellar.apps.wine.models import Wine

from .models import (
    HardwareDevice,
    OfflineOperation,
)


def get_device_from_token(request):
    """
    Extract and validate hardware device from API token.

    Returns (device, user) tuple or (None, None) if invalid.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Token "):
        token = auth_header[6:]
        try:
            device = HardwareDevice.objects.select_related("user").get(
                api_token=token,
                is_active=True,
            )
            device.last_seen = timezone.now()
            device.save(update_fields=["last_seen"])
            return device, device.user
        except HardwareDevice.DoesNotExist:
            pass
    return None, None


def hardware_auth_required(view_func):
    """Decorator to require hardware device authentication."""

    def wrapper(request, *args, **kwargs):
        device, user = get_device_from_token(request)
        if not device:
            return JsonResponse({"error": "Invalid or missing API token"}, status=401)
        request.hardware_device = device
        request.user = user
        return view_func(request, *args, **kwargs)

    return wrapper


# ============== Health Check ==============


@login_not_required
def api_health_check(request):
    """Health check endpoint for Pi client connectivity test."""
    return JsonResponse(
        {
            "status": "ok",
            "timestamp": timezone.now().isoformat(),
        }
    )


# ============== Hardware Device Management ==============


@login_required
@require_POST
def register_device(request):
    """Register a new hardware device."""
    try:
        data = json.loads(request.body)
        name = data.get("name", "Pi Device")
        device_id = data.get("device_id")
        storage_id = data.get("storage_id")

        if not device_id:
            return JsonResponse({"error": "device_id is required"}, status=400)

        # Check if device already exists
        existing = HardwareDevice.objects.filter(device_id=device_id).first()
        if existing:
            return JsonResponse({"error": "Device already registered"}, status=400)

        # Get storage if specified
        storage = None
        if storage_id:
            storage = get_object_or_404(Storage, pk=storage_id, user=request.user)

        # Generate API token
        api_token = secrets.token_urlsafe(32)

        device = HardwareDevice.objects.create(
            user=request.user,
            name=name,
            device_id=device_id,
            storage=storage,
            api_token=api_token,
        )

        return JsonResponse(
            {
                "id": device.pk,
                "name": device.name,
                "device_id": device.device_id,
                "api_token": api_token,
                "storage_id": storage.pk if storage else None,
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)


# ============== Sync Endpoints ==============


@login_not_required
@csrf_exempt
@require_POST
@hardware_auth_required
def sync_operations(request):
    """
    Sync offline operations from Pi client.

    Expects:
        - operations: List of operation dicts with:
            - operation_type: 'add_wine', 'remove_wine', etc.
            - data: Operation-specific data
            - timestamp: When operation was performed (ISO format)
    """
    try:
        data = json.loads(request.body)
        operations = data.get("operations", [])

        results = []
        for op in operations:
            op_type = op.get("operation_type")
            op_data = op.get("data", {})
            timestamp_str = op.get("timestamp")

            timestamp = timezone.now()
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(
                        timestamp_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            # Store operation record
            offline_op = OfflineOperation.objects.create(
                user=request.user,
                device=request.hardware_device,
                operation_type=op_type,
                operation_data=op_data,
                client_timestamp=timestamp,
            )

            # Try to apply the operation
            try:
                _apply_offline_operation(request.user, op_type, op_data)
                offline_op.applied = True
                offline_op.save(update_fields=["applied"])
                results.append({"id": offline_op.pk, "success": True})
            except Exception as e:
                offline_op.error = str(e)
                offline_op.save(update_fields=["error"])
                results.append({"id": offline_op.pk, "success": False, "error": str(e)})

        return JsonResponse(
            {
                "synced": len(results),
                "results": results,
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)


def _apply_offline_operation(user, op_type, op_data):
    """Apply a single offline operation."""
    if op_type == "add_wine":
        wine_id = op_data.get("wine_id")
        rack_id = op_data.get("rack_id")
        row = op_data.get("row")
        col = op_data.get("col")

        if not all([wine_id, rack_id, row, col]):
            raise ValueError("Missing required fields for add_wine")

        wine = get_object_or_404(Wine, pk=wine_id, user=user)
        storage = get_object_or_404(Storage, pk=rack_id, user=user)

        StorageItem.objects.create(
            user=user,
            storage=storage,
            wine=wine,
            row=row,
            column=col,
        )

    elif op_type == "remove_wine":
        rack_id = op_data.get("rack_id")
        row = op_data.get("row")
        col = op_data.get("col")

        if not all([rack_id, row, col]):
            raise ValueError("Missing required fields for remove_wine")

        storage = get_object_or_404(Storage, pk=rack_id, user=user)

        StorageItem.objects.filter(
            storage=storage,
            row=row,
            column=col,
            deleted=False,
        ).update(deleted=True)

    else:
        raise ValueError(f"Unknown operation type: {op_type}")


# ============== Wine API Endpoints ==============


@login_not_required
@csrf_exempt
@require_GET
@hardware_auth_required
def get_wine_by_barcode(request, barcode):
    """Look up a wine by its barcode."""
    wine = Wine.objects.filter(
        user=request.user,
        barcode=barcode,
    ).first()

    if not wine:
        return JsonResponse({"error": "Wine not found"}, status=404)

    return JsonResponse(_wine_to_dict(wine))


@login_not_required
@csrf_exempt
@require_GET
@hardware_auth_required
def get_wine(request, wine_id):
    """Get wine by ID."""
    wine = get_object_or_404(Wine, pk=wine_id, user=request.user)
    return JsonResponse(_wine_to_dict(wine))


def _wine_to_dict(wine):
    """Convert wine model to dictionary."""
    return {
        "id": wine.pk,
        "name": wine.name,
        "barcode": wine.barcode,
        "wine_type": wine.wine_type,
        "vintage": wine.vintage,
        "country": wine.country,
        "subregion": wine.subregion,
        "producer": wine.get_vineyards,
        "grape_variety": wine.get_grapes,
        "abv": wine.abv,
        "rating": wine.rating,
        "price": float(wine.price) if wine.price else None,
    }


# ============== Storage API Endpoints ==============


@login_not_required
@csrf_exempt
@require_GET
@hardware_auth_required
def get_rack_positions(request, rack_id):
    """Get all positions for a rack."""
    storage = get_object_or_404(Storage, pk=rack_id, user=request.user)

    items = storage.items.filter(deleted=False).select_related("wine")

    # Build position map
    positions = []
    for row in range(1, storage.rows + 1):
        for col in range(1, storage.columns + 1):
            item = next((i for i in items if i.row == row and i.column == col), None)
            positions.append(
                {
                    "row": row,
                    "col": col,
                    "is_empty": item is None,
                    "wine_id": item.wine.pk if item else None,
                    "wine": _wine_to_dict(item.wine) if item else None,
                }
            )

    return JsonResponse(
        {
            "rack_id": storage.pk,
            "rack_name": storage.name,
            "rows": storage.rows,
            "columns": storage.columns,
            "positions": positions,
        }
    )


@login_not_required
@csrf_exempt
@require_GET
@hardware_auth_required
def get_position(request, rack_id, row, col):
    """Get a specific position."""
    storage = get_object_or_404(Storage, pk=rack_id, user=request.user)

    item = (
        storage.items.filter(
            row=row,
            column=col,
            deleted=False,
        )
        .select_related("wine")
        .first()
    )

    return JsonResponse(
        {
            "rack_id": storage.pk,
            "row": row,
            "col": col,
            "is_empty": item is None,
            "wine_id": item.wine.pk if item else None,
            "wine": _wine_to_dict(item.wine) if item else None,
        }
    )


@login_not_required
@csrf_exempt
@require_POST
@hardware_auth_required
def add_wine_to_position(request):
    """Add a wine to a storage position."""
    try:
        data = json.loads(request.body)
        wine_id = data.get("wine_id")
        rack_id = data.get("rack_id")
        row = data.get("row")
        col = data.get("col")

        if not all([wine_id, rack_id, row, col]):
            return JsonResponse(
                {"error": "wine_id, rack_id, row, and col are required"},
                status=400,
            )

        wine = get_object_or_404(Wine, pk=wine_id, user=request.user)
        storage = get_object_or_404(Storage, pk=rack_id, user=request.user)

        # Check if position is occupied
        if storage.is_slot_occupied(row, col):
            return JsonResponse(
                {"error": "Position is already occupied"},
                status=400,
            )

        item = StorageItem.objects.create(
            user=request.user,
            storage=storage,
            wine=wine,
            row=row,
            column=col,
        )

        return JsonResponse(
            {
                "id": item.pk,
                "rack_id": storage.pk,
                "row": row,
                "col": col,
                "wine_id": wine.pk,
                "is_empty": False,
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)


@login_not_required
@csrf_exempt
@require_POST
@hardware_auth_required
def remove_wine_from_position(request):
    """Remove a wine from a storage position."""
    try:
        data = json.loads(request.body)
        rack_id = data.get("rack_id")
        row = data.get("row")
        col = data.get("col")

        if not all([rack_id, row, col]):
            return JsonResponse(
                {"error": "rack_id, row, and col are required"},
                status=400,
            )

        storage = get_object_or_404(Storage, pk=rack_id, user=request.user)

        item = (
            storage.items.filter(
                row=row,
                column=col,
                deleted=False,
            )
            .select_related("wine")
            .first()
        )

        if not item:
            return JsonResponse({"wine": None})

        wine = item.wine
        item.deleted = True
        item.save(update_fields=["deleted"])

        return JsonResponse(
            {
                "wine": _wine_to_dict(wine),
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)


# ============== Web Views ==============


class DeviceSettingsView(LoginRequiredMixin, TemplateView):
    """Web interface for managing hardware devices."""

    template_name = "device_settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        devices = (
            HardwareDevice.objects.filter(user=self.request.user)
            .select_related("storage")
            .order_by("-created")
        )

        storages = Storage.objects.filter(user=self.request.user)

        context["devices"] = devices
        context["storages"] = storages
        context["new_token"] = self.request.session.pop("new_device_token", None)
        return context

    def post(self, request, *args, **kwargs):
        """Handle device registration and management."""
        action = request.POST.get("action")

        if action == "register":
            name = request.POST.get("name", "Pi Device")
            device_id = request.POST.get("device_id")
            storage_id = request.POST.get("storage_id")

            if not device_id:
                messages.error(request, _("Device ID is required"))
                return redirect("hardware:device-settings")

            # Check if device already exists
            if HardwareDevice.objects.filter(device_id=device_id).exists():
                messages.error(request, _("Device ID already registered"))
                return redirect("hardware:device-settings")

            storage = None
            if storage_id:
                storage = get_object_or_404(Storage, pk=storage_id, user=request.user)

            api_token = secrets.token_urlsafe(32)

            HardwareDevice.objects.create(
                user=request.user,
                name=name,
                device_id=device_id,
                storage=storage,
                api_token=api_token,
            )

            # Store token in session to display once
            request.session["new_device_token"] = api_token
            messages.success(request, _("Device registered successfully"))

        elif action == "toggle":
            device_id = request.POST.get("device_pk")
            device = get_object_or_404(HardwareDevice, pk=device_id, user=request.user)
            device.is_active = not device.is_active
            device.save(update_fields=["is_active"])
            status = _("activated") if device.is_active else _("deactivated")
            messages.success(request, _("Device %(status)s") % {"status": status})

        elif action == "delete":
            device_id = request.POST.get("device_pk")
            device = get_object_or_404(HardwareDevice, pk=device_id, user=request.user)
            device.delete()
            messages.success(request, _("Device deleted"))

        return redirect("hardware:device-settings")
