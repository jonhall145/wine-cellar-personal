"""REST API endpoints for PWA offline data access.

Provides JSON endpoints for the service worker to cache and serve
cellar data when offline. All endpoints require authentication and
scope data to the user's active household.
"""

import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from wine_cellar.apps.user.views import get_active_household, get_user_settings

logger = logging.getLogger(__name__)


def _storage_item_to_dict(item, beverage_fk):
    """Serialize a StorageItem to a dict."""
    beverage = getattr(item, beverage_fk)
    return {
        "id": item.pk,
        "beverage_id": beverage.pk,
        "storage_id": item.storage_id,
        "storage_name": item.storage.name if item.storage else "",
        "row": item.row,
        "column": item.column,
        "price": str(item.price) if item.price else None,
        "is_gift": item.is_gift,
        "gift_from": item.gift_from or "",
        "occasion": item.occasion or "",
        "rating": item.rating,
    }


def _storage_to_dict(storage):
    """Serialize a Storage to a dict."""
    return {
        "id": storage.pk,
        "name": storage.name,
        "location": storage.location,
        "rows": storage.rows,
        "columns": storage.columns,
        "is_cold": storage.is_cold,
        "order": storage.order,
        "is_default": storage.is_default,
    }


def _wine_to_dict(wine):
    """Serialize a Wine to a dict for offline access."""
    return {
        "id": wine.pk,
        "name": wine.name,
        "type": wine.get_type if wine.wine_type else "",
        "type_code": wine.wine_type,
        "category": wine.get_category or "",
        "country": wine.country,
        "country_name": wine.country_name,
        "subregion": wine.subregion or "",
        "appellation": str(wine.appellation) if wine.appellation else "",
        "vintage": wine.vintage,
        "grapes": [str(g) for g in wine.grapes.all()],
        "attributes": [str(a) for a in wine.attributes.all()],
        "food_pairings": [str(f) for f in wine.food_pairings.all()],
        "abv": wine.abv,
        "rating": wine.rating,
        "price": str(wine.price) if wine.price else None,
        "size": str(wine.size) if wine.size else "",
        "drink_from": wine.drink_from,
        "drink_to": wine.drink_to,
        "comment": wine.comment,
        "stock_count": getattr(wine, "stock_count", 0),
        "image": wine.image_thumbnail or "",
        "modified": wine.modified.isoformat() if wine.modified else "",
    }


def _whisky_to_dict(whisky):
    """Serialize a Whisky to a dict for offline access."""
    return {
        "id": whisky.pk,
        "name": whisky.name,
        "type": whisky.get_whisky_type_display(),
        "type_code": whisky.whisky_type,
        "distillery": str(whisky.distillery) if whisky.distillery else "",
        "region": str(whisky.region) if whisky.region else "",
        "country": whisky.country,
        "age_statement": whisky.age_statement,
        "vintage_year": whisky.vintage_year,
        "bottled_year": whisky.bottled_year,
        "abv": whisky.abv,
        "size": whisky.get_size_display(),
        "peated_level": (
            whisky.get_peated_level_display() if whisky.peated_level else ""
        ),
        "cask_type": whisky.cask_type,
        "cask_strength": whisky.cask_strength,
        "bottler": str(whisky.bottler) if whisky.bottler else "",
        "rating": whisky.rating,
        "price": str(whisky.price) if whisky.price else None,
        "comment": whisky.comment,
        "stock_count": getattr(whisky, "stock_count", 0),
        "image": whisky.image_thumbnail or "",
        "modified": whisky.modified.isoformat() if whisky.modified else "",
    }


@require_GET
def api_cellar_sync(request):
    """Return full cellar data for offline caching.

    Accepts optional `since` query param (ISO datetime) to return
    only records modified after that timestamp (for incremental sync).
    Returns beverages, storage items, and storages in a single payload.
    """
    from django.utils.dateparse import parse_datetime
    from django.utils.timezone import is_aware, make_aware

    household = get_active_household(request.user)
    app_type = getattr(settings, "CELLAR_APP_TYPE", "wine")
    user_settings = get_user_settings(request.user)
    since_raw = request.GET.get("since")
    since = None

    if since_raw:
        since = parse_datetime(since_raw)
        if since is None:
            return JsonResponse(
                {
                    "error": "Invalid 'since' datetime format."
                    " Expected ISO 8601 (e.g. 2024-03-13T10:30:00Z)."
                },
                status=400,
            )
        if not is_aware(since):
            since = make_aware(since)

    if app_type == "whisky":
        from wine_cellar.apps.whisky.models import Whisky, WhiskyStorageItem

        qs = (
            Whisky.objects.filter(household=household, deleted=False)
            .with_related()
            .with_stock_count()
        )
        if since:
            qs = qs.filter(modified__gt=since)

        beverages = [_whisky_to_dict(w) for w in qs]

        items_qs = WhiskyStorageItem.objects.filter(
            household=household, deleted=False
        ).select_related("storage", "whisky")
        if since:
            items_qs = items_qs.filter(modified__gt=since)

        stock_items = [_storage_item_to_dict(i, "whisky") for i in items_qs]
    else:
        from wine_cellar.apps.storage.models import StorageItem
        from wine_cellar.apps.wine.models import Wine

        qs = (
            Wine.objects.filter(household=household, deleted=False)
            .with_related()
            .with_stock_count()
        )
        if since:
            qs = qs.filter(modified__gt=since)

        beverages = [_wine_to_dict(w) for w in qs]

        items_qs = StorageItem.objects.filter(
            household=household, deleted=False
        ).select_related("storage", "wine")
        if since:
            items_qs = items_qs.filter(modified__gt=since)

        stock_items = [_storage_item_to_dict(i, "wine") for i in items_qs]

    from wine_cellar.apps.storage.models import Storage

    storages_qs = Storage.objects.filter(
        household=household, app_type=app_type
    ).order_by("order", "name")
    storages = [_storage_to_dict(s) for s in storages_qs]

    return JsonResponse(
        {
            "app_type": app_type,
            "currency": user_settings.currency if user_settings else "EUR",
            "beverages": beverages,
            "stock_items": stock_items,
            "storages": storages,
            "is_incremental": bool(since_raw),
        }
    )


@require_POST
def api_push_subscribe(request):
    """Save a Web Push subscription for the current user."""
    from wine_cellar.apps.user.models import PushSubscription

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    endpoint = data.get("endpoint")
    keys = data.get("keys", {})
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")

    if not all([endpoint, p256dh, auth]):
        return JsonResponse({"error": "Missing subscription data"}, status=400)

    PushSubscription.objects.update_or_create(
        user=request.user,
        endpoint=endpoint,
        defaults={"p256dh": p256dh, "auth": auth},
    )

    return JsonResponse({"ok": True})


@require_POST
def api_push_unsubscribe(request):
    """Remove a Web Push subscription for the current user."""
    from wine_cellar.apps.user.models import PushSubscription

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    endpoint = data.get("endpoint")
    if not endpoint:
        return JsonResponse({"error": "Missing endpoint"}, status=400)

    PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()

    return JsonResponse({"ok": True})


@require_GET
def api_vapid_public_key(request):
    """Return the VAPID public key for push subscription."""
    key = getattr(settings, "VAPID_PUBLIC_KEY", "")
    return JsonResponse({"public_key": key})
