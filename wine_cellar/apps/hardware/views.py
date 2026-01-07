"""API views for hardware (Raspberry Pi) integration."""

import json
import secrets
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from wine_cellar.apps.storage.models import Storage, StorageItem
from wine_cellar.apps.wine.models import Wine, WineImage, ImageType, Grape, Size
from wine_cellar.apps.wine.services.vision_extraction import WineVisionExtractor

from .models import (
    PositionChangeReview,
    RackSnapshot,
    HardwareDevice,
    OfflineOperation,
    ChangeType,
    ReviewStatus,
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

def api_health_check(request):
    """Health check endpoint for Pi client connectivity test."""
    return JsonResponse({
        "status": "ok",
        "timestamp": timezone.now().isoformat(),
    })


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

        return JsonResponse({
            "id": device.pk,
            "name": device.name,
            "device_id": device.device_id,
            "api_token": api_token,
            "storage_id": storage.pk if storage else None,
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)


# ============== Position Change Endpoints ==============

@csrf_exempt
@require_POST
@hardware_auth_required
def report_position_change(request):
    """
    Report a detected position change from Pi client.

    Expects:
        - rack_id: Storage ID
        - row: Detected row (-1 if unknown)
        - col: Detected column (-1 if unknown)
        - change_type: 'added', 'removed', or 'reconciliation'
        - wine_id: Wine ID (optional)
        - confidence: Detection confidence 0.0-1.0
        - image: Snapshot image (optional, multipart)
    """
    try:
        # Handle both JSON and multipart form data
        if request.content_type and "multipart" in request.content_type:
            rack_id = int(request.POST.get("rack_id", 0))
            row = int(request.POST.get("row", -1))
            col = int(request.POST.get("col", -1))
            change_type = request.POST.get("change_type", "")
            wine_id = request.POST.get("wine_id")
            confidence = float(request.POST.get("confidence", 0.0))
            image_file = request.FILES.get("image")
        else:
            data = json.loads(request.body)
            rack_id = data.get("rack_id", 0)
            row = data.get("row", -1)
            col = data.get("col", -1)
            change_type = data.get("change_type", "")
            wine_id = data.get("wine_id")
            confidence = data.get("confidence", 0.0)
            image_file = None

        # Validate storage
        storage = get_object_or_404(
            Storage,
            pk=rack_id,
            user=request.user,
        )

        # Validate change type
        if change_type not in [c[0] for c in ChangeType.choices]:
            return JsonResponse({"error": "Invalid change_type"}, status=400)

        # Get wine if specified
        wine = None
        if wine_id:
            wine = Wine.objects.filter(pk=wine_id, user=request.user).first()

        # Create review record
        review = PositionChangeReview.objects.create(
            user=request.user,
            storage=storage,
            wine=wine,
            row=row if row >= 0 else None,
            column=col if col >= 0 else None,
            change_type=change_type,
            confidence=confidence,
        )

        # Attach image if provided
        if image_file:
            review.image.save(
                f"change_{review.pk}.jpg",
                image_file,
            )

        # Auto-apply if high confidence and valid position
        if confidence >= 0.9 and row >= 0 and col >= 0:
            review.status = ReviewStatus.AUTO_APPLIED
            review.final_row = row
            review.final_column = col
            review.reviewed_at = timezone.now()
            review.save()

            # Apply the change
            _apply_position_change(review)

        return JsonResponse({
            "id": review.pk,
            "status": review.status,
            "auto_applied": review.status == ReviewStatus.AUTO_APPLIED,
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


def _apply_position_change(review):
    """Apply a position change to the database."""
    if review.change_type == ChangeType.ADDED and review.wine:
        # Add bottle to position
        StorageItem.objects.create(
            user=review.user,
            storage=review.storage,
            wine=review.wine,
            row=review.final_row,
            column=review.final_column,
        )
    elif review.change_type == ChangeType.REMOVED:
        # Remove bottle from position
        StorageItem.objects.filter(
            storage=review.storage,
            row=review.final_row,
            column=review.final_column,
            deleted=False,
        ).update(deleted=True)


@csrf_exempt
@require_GET
@hardware_auth_required
def get_pending_reviews(request):
    """Get position changes pending user review."""
    reviews = PositionChangeReview.objects.filter(
        user=request.user,
        status=ReviewStatus.PENDING,
    ).select_related("storage", "wine")

    result = []
    for review in reviews:
        result.append({
            "id": review.pk,
            "storage_id": review.storage.pk,
            "storage_name": review.storage.name,
            "wine_id": review.wine.pk if review.wine else None,
            "wine_name": review.wine.name if review.wine else None,
            "row": review.row,
            "column": review.column,
            "change_type": review.change_type,
            "confidence": review.confidence,
            "image_url": review.image.url if review.image else None,
            "created": review.created.isoformat(),
        })

    return JsonResponse({"reviews": result})


@login_required
@require_POST
def approve_review(request, review_id):
    """Approve a position change review."""
    try:
        data = json.loads(request.body)
        final_row = data.get("row")
        final_column = data.get("column")

        review = get_object_or_404(
            PositionChangeReview,
            pk=review_id,
            user=request.user,
            status=ReviewStatus.PENDING,
        )

        review.status = ReviewStatus.APPROVED
        review.final_row = final_row if final_row is not None else review.row
        review.final_column = final_column if final_column is not None else review.column
        review.reviewed_at = timezone.now()
        review.save()

        # Apply the change
        if review.final_row is not None and review.final_column is not None:
            _apply_position_change(review)

        return JsonResponse({"success": True})

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)


@login_required
@require_POST
def reject_review(request, review_id):
    """Reject a position change review."""
    review = get_object_or_404(
        PositionChangeReview,
        pk=review_id,
        user=request.user,
        status=ReviewStatus.PENDING,
    )

    review.status = ReviewStatus.REJECTED
    review.reviewed_at = timezone.now()
    review.save()

    return JsonResponse({"success": True})


# ============== Rack Snapshot Endpoints ==============

@csrf_exempt
@require_POST
@hardware_auth_required
def upload_rack_snapshot(request):
    """
    Upload a rack snapshot from Pi client.

    Expects multipart form with:
        - rack_id: Storage ID
        - image: Snapshot image
        - grid_state: JSON string of detected grid state (optional)
    """
    rack_id = request.POST.get("rack_id")
    image_file = request.FILES.get("image")
    grid_state_str = request.POST.get("grid_state")

    if not rack_id or not image_file:
        return JsonResponse(
            {"error": "rack_id and image are required"},
            status=400,
        )

    storage = get_object_or_404(
        Storage,
        pk=rack_id,
        user=request.user,
    )

    grid_state = None
    if grid_state_str:
        try:
            grid_state = json.loads(grid_state_str)
        except json.JSONDecodeError:
            pass

    # Compute discrepancies if grid state provided
    discrepancies = None
    if grid_state and "occupied" in grid_state:
        discrepancies = _compute_discrepancies(storage, grid_state)

    snapshot = RackSnapshot.objects.create(
        user=request.user,
        storage=storage,
        grid_state=grid_state,
        discrepancies=discrepancies,
    )
    snapshot.image.save(
        f"snapshot_{snapshot.pk}.jpg",
        image_file,
    )

    return JsonResponse({
        "id": snapshot.pk,
        "has_discrepancies": bool(discrepancies),
        "discrepancy_count": len(discrepancies) if discrepancies else 0,
    })


def _compute_discrepancies(storage, grid_state):
    """Compare detected grid state with database."""
    discrepancies = []
    occupied = grid_state.get("occupied", [])

    # Get current database state
    items = storage.items.filter(deleted=False)
    db_positions = {(item.row, item.column) for item in items}

    # Check each cell
    for row_idx, row in enumerate(occupied):
        for col_idx, is_occupied in enumerate(row):
            db_row = row_idx + 1  # 1-indexed in DB
            db_col = col_idx + 1
            db_occupied = (db_row, db_col) in db_positions

            if is_occupied != db_occupied:
                discrepancies.append({
                    "row": db_row,
                    "column": db_col,
                    "camera_says": "occupied" if is_occupied else "empty",
                    "database_says": "occupied" if db_occupied else "empty",
                })

    return discrepancies if discrepancies else None


# ============== Sync Endpoints ==============

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
                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
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

        return JsonResponse({
            "synced": len(results),
            "results": results,
        })

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


@csrf_exempt
@require_GET
@hardware_auth_required
def get_wine(request, wine_id):
    """Get wine by ID."""
    wine = get_object_or_404(Wine, pk=wine_id, user=request.user)
    return JsonResponse(_wine_to_dict(wine))


@csrf_exempt
@require_POST
@hardware_auth_required
def create_wine_from_labels(request):
    """
    Create a wine from label images using AI extraction.

    Expects multipart form with:
        - front_label: Front label image
        - back_label: Back label image (optional)
        - barcode: Barcode string (optional)
    """
    front_label = request.FILES.get("front_label")
    back_label = request.FILES.get("back_label")
    barcode = request.POST.get("barcode", "")

    if not front_label:
        return JsonResponse({"error": "front_label is required"}, status=400)

    # Convert images to base64 for vision extraction
    import base64

    images = []
    if barcode:
        # If we have barcode, we don't need to extract it from image
        pass

    front_data = base64.b64encode(front_label.read()).decode("utf-8")
    images.append(front_data)

    if back_label:
        back_data = base64.b64encode(back_label.read()).decode("utf-8")
        images.append(back_data)

    # Extract wine data from labels
    extractor = WineVisionExtractor()
    result = extractor.extract_from_images(images)

    extracted = result.get("data", {})

    # Create the wine
    wine_data = {
        "user": request.user,
        "name": extracted.get("name", f"Unknown Wine ({barcode})" if barcode else "Unknown Wine"),
        "barcode": barcode or extracted.get("barcode"),
        "wine_type": extracted.get("wine_type", "RE"),  # Default to red
        "vintage": extracted.get("vintage"),
        "country": extracted.get("country", "US"),  # Default country
        "subregion": extracted.get("subregion"),
        "abv": extracted.get("abv"),
        "category": extracted.get("sweetness"),
    }

    wine = Wine.objects.create(**wine_data)

    # Handle grapes
    grapes = extracted.get("grapes", [])
    for grape_name in grapes:
        grape, _ = Grape.objects.get_or_create(
            user=request.user,
            name=grape_name,
        )
        wine.grapes.add(grape)

    # Handle size
    size_code = extracted.get("volume")
    if size_code:
        size, _ = Size.objects.get_or_create(
            user=request.user,
            name=size_code,
        )
        wine.size = size
        wine.save(update_fields=["size"])

    # Save label images
    front_label.seek(0)
    WineImage.objects.create(
        wine=wine,
        user=request.user,
        image_type=ImageType.LABEL_FRONT,
    ).image.save("front_label.jpg", front_label)

    if back_label:
        back_label.seek(0)
        WineImage.objects.create(
            wine=wine,
            user=request.user,
            image_type=ImageType.LABEL_BACK,
        ).image.save("back_label.jpg", back_label)

    return JsonResponse({
        **_wine_to_dict(wine),
        "extraction_confidence": result.get("confidence", "low"),
        "extracted_fields": result.get("extracted_fields", []),
    })


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
            item = next(
                (i for i in items if i.row == row and i.column == col),
                None
            )
            positions.append({
                "row": row,
                "col": col,
                "is_empty": item is None,
                "wine_id": item.wine.pk if item else None,
                "wine": _wine_to_dict(item.wine) if item else None,
            })

    return JsonResponse({
        "rack_id": storage.pk,
        "rack_name": storage.name,
        "rows": storage.rows,
        "columns": storage.columns,
        "positions": positions,
    })


@csrf_exempt
@require_GET
@hardware_auth_required
def get_position(request, rack_id, row, col):
    """Get a specific position."""
    storage = get_object_or_404(Storage, pk=rack_id, user=request.user)

    item = storage.items.filter(
        row=row,
        column=col,
        deleted=False,
    ).select_related("wine").first()

    return JsonResponse({
        "rack_id": storage.pk,
        "row": row,
        "col": col,
        "is_empty": item is None,
        "wine_id": item.wine.pk if item else None,
        "wine": _wine_to_dict(item.wine) if item else None,
    })


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

        return JsonResponse({
            "id": item.pk,
            "rack_id": storage.pk,
            "row": row,
            "col": col,
            "wine_id": wine.pk,
            "is_empty": False,
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)


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

        item = storage.items.filter(
            row=row,
            column=col,
            deleted=False,
        ).select_related("wine").first()

        if not item:
            return JsonResponse({"wine": None})

        wine = item.wine
        item.deleted = True
        item.save(update_fields=["deleted"])

        return JsonResponse({
            "wine": _wine_to_dict(wine),
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
