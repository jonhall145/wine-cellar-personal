import base64
import json
import os

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone

BACKUP_FORMAT_VERSION = 1
BACKUP_CONTENT_TYPE = "application/json"

USER_SETTINGS_FIELDS = [
    "currency",
    "notifications",
    "reminder_enabled",
    "reminder_years_before",
]
HOUSEHOLD_SETTINGS_FIELDS = ["currency", "notifications"]
STORAGE_FIELDS = [
    "name",
    "description",
    "location",
    "rows",
    "columns",
    "is_cold",
    "order",
    "is_default",
    "cell_mask",
    "created",
    "modified",
]
WINE_REFERENCE_FIELDS = {
    "sizes": ["name", "created", "modified"],
    "grapes": ["name", "created", "modified"],
    "attributes": ["name", "created", "modified"],
    "food_pairings": ["name", "created", "modified"],
    "vineyards": ["name", "website", "region", "country", "created", "modified"],
    "sources": ["name", "url", "price_selector", "created", "modified"],
}
WINE_FIELDS = [
    "name",
    "wine_type",
    "category",
    "abv",
    "vintage",
    "drink_by",
    "drink_from",
    "drink_to",
    "comment",
    "rating",
    "country",
    "subregion",
    "price",
    "price_url",
    "deleted",
    "created",
    "modified",
]
COLLECTION_FIELDS = ["name", "description", "color", "icon", "created", "modified"]
WINE_STORAGE_ITEM_FIELDS = [
    "row",
    "column",
    "deleted",
    "price",
    "is_gift",
    "gift_from",
    "occasion",
    "rating",
    "finished_date",
    "recipient",
    "given_occasion",
    "given_date",
    "removal_reason",
    "created",
    "modified",
]
WINE_WISHLIST_FIELDS = [
    "name",
    "wine_type",
    "country",
    "subregion",
    "vintage",
    "price_limit",
    "notes",
    "priority",
    "purchased",
    "created",
    "modified",
]
WINE_BOTTLE_NOTE_FIELDS = ["note_date", "note", "created", "modified"]
WINE_DRINK_RECORD_FIELDS = [
    "date_consumed",
    "tasting_notes",
    "rating",
    "shared_with",
    "occasion",
    "created",
    "modified",
]
WINE_ALERT_FIELDS = ["alert_date", "message", "is_read", "created", "modified"]
WINE_REMINDER_FIELDS = ["min_stock", "is_active", "created", "modified"]
WINE_PRICE_HISTORY_FIELDS = ["price", "recorded_at", "created", "modified"]
WHISKY_REFERENCE_FIELDS = {
    "attributes": ["name", "created", "modified"],
    "sources": ["name", "url", "created", "modified"],
}
WHISKY_FIELDS = [
    "name",
    "whisky_type",
    "country",
    "age_statement",
    "vintage_year",
    "bottled_year",
    "abv",
    "size",
    "peated_level",
    "cask_type",
    "cask_strength",
    "color",
    "bottler_series",
    "cask_number",
    "batch_number",
    "bottle_number",
    "limited_edition",
    "release_year",
    "rating",
    "price",
    "comment",
    "owner",
    "deleted",
    "created",
    "modified",
]
WHISKY_CASK_HISTORY_FIELDS = [
    "order",
    "cask_type",
    "wood_type",
    "previous_contents",
    "duration_years",
    "is_finish",
    "cask_number",
    "description",
]
WHISKY_STORAGE_ITEM_FIELDS = [
    "row",
    "column",
    "deleted",
    "price",
    "is_gift",
    "gift_from",
    "occasion",
    "rating",
    "fill_level",
    "opened_date",
    "dreg_date",
    "owner",
    "finished_date",
    "recipient",
    "given_occasion",
    "given_date",
    "removal_reason",
    "created",
    "modified",
]
WHISKY_WISHLIST_FIELDS = [
    "name",
    "whisky_type",
    "country",
    "age_statement",
    "price_limit",
    "notes",
    "priority",
    "purchased",
    "created",
    "modified",
]
WHISKY_BOTTLE_NOTE_FIELDS = ["note_date", "note", "created", "modified"]
WHISKY_DRINK_RECORD_FIELDS = [
    "date_consumed",
    "tasting_notes",
    "rating",
    "shared_with",
    "occasion",
    "created",
    "modified",
]
WHISKY_ALERT_FIELDS = ["alert_date", "message", "is_read", "created", "modified"]
WHISKY_REMINDER_FIELDS = ["min_stock", "is_active", "created", "modified"]
WHISKY_PRICE_HISTORY_FIELDS = ["price", "recorded_at", "created", "modified"]
MOVE_HISTORY_FIELDS = [
    "from_row",
    "from_column",
    "to_row",
    "to_column",
    "moved_at",
]


class BackupImportError(Exception):
    pass


def build_backup_response(user, household) -> HttpResponse:
    payload = export_backup_payload(user, household)
    app_type = payload["app_type"]
    today = timezone.localdate().isoformat()
    response = HttpResponse(
        json.dumps(payload, indent=2, cls=DjangoJSONEncoder, ensure_ascii=False),
        content_type=BACKUP_CONTENT_TYPE,
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{app_type}_backup_{today}.json"'
    )
    return response


def export_backup_payload(user, household) -> dict:
    payload = {
        "format_version": BACKUP_FORMAT_VERSION,
        "app_type": _get_app_type(),
        "exported_at": timezone.now(),
        "household": {"name": household.name},
        "user_settings": _export_simple_fields(
            user.user_settings, USER_SETTINGS_FIELDS
        ),
        "household_settings": _export_simple_fields(
            household.settings if hasattr(household, "settings") else None,
            HOUSEHOLD_SETTINGS_FIELDS,
        ),
    }
    if payload["app_type"] == "whisky":
        payload["data"] = _export_whisky_backup(user, household)
    else:
        payload["data"] = _export_wine_backup(user, household)
    return payload


def restore_backup_file(uploaded_file, *, user, household) -> dict:
    try:
        raw = uploaded_file.read()
        payload = json.loads(raw.decode("utf-8"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupImportError("Upload a valid JSON backup file.") from exc
    return restore_backup_payload(payload, user=user, household=household)


def restore_backup_payload(payload: dict, *, user, household) -> dict:
    if not isinstance(payload, dict):
        raise BackupImportError("Backup file must contain a JSON object.")
    if payload.get("format_version") != BACKUP_FORMAT_VERSION:
        raise BackupImportError("Unsupported backup format.")
    app_type = payload.get("app_type")
    if app_type != _get_app_type():
        raise BackupImportError("This backup was created for a different app type.")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise BackupImportError("Backup file is missing its data section.")

    with transaction.atomic():
        _restore_settings(payload, user=user, household=household)
        if app_type == "whisky":
            return _restore_whisky_backup(data, user=user, household=household)
        return _restore_wine_backup(data, user=user, household=household)


def _get_app_type() -> str:
    return getattr(settings, "CELLAR_APP_TYPE", "wine")


def _export_simple_fields(instance, fields: list[str]) -> dict:
    if instance is None:
        return {}
    return {field: getattr(instance, field) for field in fields}


def _build_field_values(model_class, payload: dict, fields: list[str]) -> dict:
    values = {}
    for field_name in fields:
        if field_name not in payload:
            continue
        field = model_class._meta.get_field(field_name)
        values[field_name] = field.to_python(payload[field_name])
    return values


def _restore_timestamps(instance, payload: dict, field_names: list[str]) -> None:
    updates = {}
    for field_name in field_names:
        if payload.get(field_name) in (None, ""):
            continue
        field = instance._meta.get_field(field_name)
        updates[field_name] = field.to_python(payload[field_name])
    if updates:
        instance.__class__.objects.filter(pk=instance.pk).update(**updates)
        for field_name, value in updates.items():
            setattr(instance, field_name, value)


def _restore_file(field_file, file_payload: dict | None) -> None:
    if not file_payload or not file_payload.get("data"):
        return
    filename = file_payload.get("name") or "backup-file"
    content = ContentFile(base64.b64decode(file_payload["data"]))
    field_file.save(filename, content, save=False)


def _export_file(field_file) -> dict | None:
    if not field_file:
        return None
    try:
        with field_file.open("rb") as uploaded:
            content = uploaded.read()
    except FileNotFoundError:
        return None
    return {
        "name": os.path.basename(field_file.name),
        "data": base64.b64encode(content).decode("ascii"),
    }


def _require_mapping(mapping: dict, backup_id, label: str):
    if backup_id in (None, ""):
        return None
    value = mapping.get(backup_id)
    if value is None:
        raise BackupImportError(
            f"Backup file contains an unknown {label} reference: {backup_id}."
        )
    return value


def _require_many(mapping: dict, backup_ids: list, label: str) -> list:
    return [_require_mapping(mapping, backup_id, label) for backup_id in backup_ids]


def _export_reference_items(queryset, fields: list[str]) -> list[dict]:
    return [
        {"backup_id": obj.pk, **_export_simple_fields(obj, fields)}
        for obj in queryset.order_by("pk")
    ]


def _export_move_histories(queryset) -> list[dict]:
    return [
        {
            "storage_item": history.storage_item_id,
            "from_storage": history.from_storage_id,
            "to_storage": history.to_storage_id,
            **_export_simple_fields(history, MOVE_HISTORY_FIELDS),
        }
        for history in queryset.order_by("pk")
    ]


def _export_wine_backup(user, household) -> dict:
    from wine_cellar.apps.storage.models import BottleMoveHistory, Storage, StorageItem
    from wine_cellar.apps.wine.models import (
        Appellation,
        Attribute,
        BottleNote,
        Collection,
        DrinkingWindowAlert,
        DrinkRecord,
        FoodPairing,
        Grape,
        PriceHistory,
        ReorderReminder,
        Size,
        Source,
        Vineyard,
        Wine,
        Wishlist,
    )

    storages = Storage.objects.filter(household=household, app_type="wine").order_by(
        "pk"
    )
    wines = Wine.objects.filter(household=household).prefetch_related(
        "grapes",
        "attributes",
        "food_pairings",
        "vineyard",
        "source",
        "wineimage_set",
        "barcodes",
    )
    collections = Collection.objects.filter(household=household).prefetch_related(
        "wines"
    )
    storage_items = StorageItem.objects.filter(household=household).select_related(
        "wine",
        "storage",
    )

    return {
        "storages": [
            {"backup_id": storage.pk, **_export_simple_fields(storage, STORAGE_FIELDS)}
            for storage in storages
        ],
        "references": {
            "sizes": _export_reference_items(
                Size.objects.filter(household=household), WINE_REFERENCE_FIELDS["sizes"]
            ),
            "grapes": _export_reference_items(
                Grape.objects.filter(household=household),
                WINE_REFERENCE_FIELDS["grapes"],
            ),
            "attributes": _export_reference_items(
                Attribute.objects.filter(household=household),
                WINE_REFERENCE_FIELDS["attributes"],
            ),
            "food_pairings": _export_reference_items(
                FoodPairing.objects.filter(household=household),
                WINE_REFERENCE_FIELDS["food_pairings"],
            ),
            "vineyards": _export_reference_items(
                Vineyard.objects.filter(household=household),
                WINE_REFERENCE_FIELDS["vineyards"],
            ),
            "sources": _export_reference_items(
                Source.objects.filter(household=household),
                WINE_REFERENCE_FIELDS["sources"],
            ),
        },
        "wines": [
            {
                "backup_id": wine.pk,
                **_export_simple_fields(wine, WINE_FIELDS),
                "size": wine.size_id,
                "appellation": (
                    {
                        "name": wine.appellation.name,
                        "country": wine.appellation.country,
                        "latitude": wine.appellation.latitude,
                        "longitude": wine.appellation.longitude,
                    }
                    if isinstance(wine.appellation, Appellation)
                    else None
                ),
                "grapes": list(wine.grapes.values_list("pk", flat=True)),
                "attributes": list(wine.attributes.values_list("pk", flat=True)),
                "food_pairings": list(wine.food_pairings.values_list("pk", flat=True)),
                "vineyard": list(wine.vineyard.values_list("pk", flat=True)),
                "source": list(wine.source.values_list("pk", flat=True)),
                "barcodes": [
                    {"barcode": barcode.barcode, "created": barcode.created}
                    for barcode in wine.barcodes.all().order_by("pk")
                ],
                "images": [
                    {
                        "image_type": image.image_type,
                        "is_primary": image.is_primary,
                        "image": _export_file(image.image),
                        "thumbnail": _export_file(image.thumbnail),
                    }
                    for image in wine.wineimage_set.all().order_by("pk")
                ],
            }
            for wine in wines.order_by("pk")
        ],
        "collections": [
            {
                "backup_id": collection.pk,
                **_export_simple_fields(collection, COLLECTION_FIELDS),
                "wines": list(collection.wines.values_list("pk", flat=True)),
            }
            for collection in collections.order_by("pk")
        ],
        "storage_items": [
            {
                "backup_id": item.pk,
                "storage": item.storage_id,
                "wine": item.wine_id,
                **_export_simple_fields(item, WINE_STORAGE_ITEM_FIELDS),
            }
            for item in storage_items.order_by("pk")
        ],
        "wishlists": [
            {"backup_id": item.pk, **_export_simple_fields(item, WINE_WISHLIST_FIELDS)}
            for item in Wishlist.objects.filter(household=household).order_by("pk")
        ],
        "bottle_notes": [
            {
                "backup_id": note.pk,
                "storage_item": note.storage_item_id,
                **_export_simple_fields(note, WINE_BOTTLE_NOTE_FIELDS),
            }
            for note in BottleNote.objects.filter(household=household).order_by("pk")
        ],
        "drink_records": [
            {
                "backup_id": record.pk,
                "wine": record.wine_id,
                "storage_item": record.storage_item_id,
                **_export_simple_fields(record, WINE_DRINK_RECORD_FIELDS),
            }
            for record in DrinkRecord.objects.filter(household=household).order_by("pk")
        ],
        "alerts": [
            {
                "backup_id": alert.pk,
                "wine": alert.wine_id,
                **_export_simple_fields(alert, WINE_ALERT_FIELDS),
            }
            for alert in DrinkingWindowAlert.objects.filter(
                household=household
            ).order_by("pk")
        ],
        "reorder_reminders": [
            {
                "backup_id": reminder.pk,
                "wine": reminder.wine_id,
                **_export_simple_fields(reminder, WINE_REMINDER_FIELDS),
            }
            for reminder in ReorderReminder.objects.filter(
                household=household
            ).order_by("pk")
        ],
        "price_history": [
            {
                "backup_id": record.pk,
                "wine": record.wine_id,
                "source": record.source_id,
                **_export_simple_fields(record, WINE_PRICE_HISTORY_FIELDS),
            }
            for record in PriceHistory.objects.filter(household=household).order_by(
                "pk"
            )
        ],
        "move_history": _export_move_histories(
            BottleMoveHistory.objects.filter(
                storage_item__household=household
            ).select_related(
                "storage_item",
                "from_storage",
                "to_storage",
            )
        ),
    }


def _export_whisky_backup(user, household) -> dict:
    from wine_cellar.apps.storage.models import Storage
    from wine_cellar.apps.whisky.models import (
        Bottler,
        Collection,
        Distillery,
        Whisky,
        WhiskyAttribute,
        WhiskyBottleMoveHistory,
        WhiskyBottleNote,
        WhiskyDrinkingWindowAlert,
        WhiskyDrinkRecord,
        WhiskyPriceHistory,
        WhiskyRegion,
        WhiskyReorderReminder,
        WhiskySource,
        WhiskyStorageItem,
        WhiskyWishlist,
    )

    whiskies = Whisky.objects.filter(household=household).prefetch_related(
        "attributes",
        "images",
        "barcodes",
        "cask_history",
    )

    regions = {
        region.pk: region
        for region in WhiskyRegion.objects.filter(
            pk__in=filter(None, whiskies.values_list("region_id", flat=True))
        )
    }
    distilleries = {
        distillery.pk: distillery
        for distillery in Distillery.objects.filter(
            pk__in=filter(None, whiskies.values_list("distillery_id", flat=True))
        )
    }
    bottlers = {
        bottler.pk: bottler
        for bottler in Bottler.objects.filter(
            pk__in=filter(None, whiskies.values_list("bottler_id", flat=True))
        )
    }
    for wishlist in WhiskyWishlist.objects.filter(household=household):
        if wishlist.region_id:
            regions[wishlist.region_id] = wishlist.region
        if wishlist.distillery_id:
            distilleries[wishlist.distillery_id] = wishlist.distillery

    return {
        "storages": [
            {"backup_id": storage.pk, **_export_simple_fields(storage, STORAGE_FIELDS)}
            for storage in Storage.objects.filter(
                household=household,
                app_type="whisky",
            ).order_by("pk")
        ],
        "references": {
            "attributes": _export_reference_items(
                WhiskyAttribute.objects.filter(household=household),
                WHISKY_REFERENCE_FIELDS["attributes"],
            ),
            "sources": _export_reference_items(
                WhiskySource.objects.filter(household=household),
                WHISKY_REFERENCE_FIELDS["sources"],
            ),
            "regions": [
                {
                    "backup_id": region.pk,
                    **_export_simple_fields(
                        region,
                        [
                            "name",
                            "slug",
                            "country",
                            "latitude",
                            "longitude",
                            "description",
                            "order",
                        ],
                    ),
                }
                for region in sorted(regions.values(), key=lambda region: region.pk)
            ],
            "distilleries": [
                {
                    "backup_id": distillery.pk,
                    **_export_simple_fields(
                        distillery,
                        [
                            "name",
                            "country",
                            "latitude",
                            "longitude",
                            "status",
                            "founded_year",
                            "closed_year",
                            "owner",
                            "description",
                            "is_user_created",
                        ],
                    ),
                    "region": distillery.region_id,
                }
                for distillery in sorted(
                    distilleries.values(),
                    key=lambda distillery: distillery.pk,
                )
            ],
            "bottlers": [
                {
                    "backup_id": bottler.pk,
                    **_export_simple_fields(
                        bottler,
                        [
                            "name",
                            "short_name",
                            "country",
                            "website",
                            "description",
                            "is_user_created",
                        ],
                    ),
                }
                for bottler in sorted(bottlers.values(), key=lambda bottler: bottler.pk)
            ],
        },
        "whiskies": [
            {
                "backup_id": whisky.pk,
                **_export_simple_fields(whisky, WHISKY_FIELDS),
                "region": whisky.region_id,
                "distillery": whisky.distillery_id,
                "bottler": whisky.bottler_id,
                "source": whisky.source_id,
                "attributes": list(whisky.attributes.values_list("pk", flat=True)),
                "barcodes": [
                    {"barcode": barcode.barcode, "created": barcode.created}
                    for barcode in whisky.barcodes.all().order_by("pk")
                ],
                "images": [
                    {
                        "image_type": image.image_type,
                        "is_primary": image.is_primary,
                        "created": image.created,
                        "image": _export_file(image.image),
                        "thumbnail": _export_file(image.thumbnail),
                    }
                    for image in whisky.images.all().order_by("pk")
                ],
                "cask_history": [
                    {
                        "backup_id": history.pk,
                        **_export_simple_fields(history, WHISKY_CASK_HISTORY_FIELDS),
                    }
                    for history in whisky.cask_history.all().order_by("pk")
                ],
            }
            for whisky in whiskies.order_by("pk")
        ],
        "collections": [
            {
                "backup_id": collection.pk,
                **_export_simple_fields(collection, COLLECTION_FIELDS),
                "whiskies": list(collection.whiskies.values_list("pk", flat=True)),
            }
            for collection in Collection.objects.filter(household=household)
            .prefetch_related("whiskies")
            .order_by("pk")
        ],
        "storage_items": [
            {
                "backup_id": item.pk,
                "storage": item.storage_id,
                "whisky": item.whisky_id,
                **_export_simple_fields(item, WHISKY_STORAGE_ITEM_FIELDS),
            }
            for item in WhiskyStorageItem.objects.filter(household=household)
            .select_related("storage", "whisky")
            .order_by("pk")
        ],
        "wishlists": [
            {
                "backup_id": item.pk,
                "distillery": item.distillery_id,
                "region": item.region_id,
                **_export_simple_fields(item, WHISKY_WISHLIST_FIELDS),
            }
            for item in WhiskyWishlist.objects.filter(household=household).order_by(
                "pk"
            )
        ],
        "bottle_notes": [
            {
                "backup_id": note.pk,
                "storage_item": note.storage_item_id,
                **_export_simple_fields(note, WHISKY_BOTTLE_NOTE_FIELDS),
            }
            for note in WhiskyBottleNote.objects.filter(household=household).order_by(
                "pk"
            )
        ],
        "drink_records": [
            {
                "backup_id": record.pk,
                "whisky": record.whisky_id,
                "storage_item": record.storage_item_id,
                **_export_simple_fields(record, WHISKY_DRINK_RECORD_FIELDS),
            }
            for record in WhiskyDrinkRecord.objects.filter(
                household=household
            ).order_by("pk")
        ],
        "alerts": [
            {
                "backup_id": alert.pk,
                "whisky": alert.whisky_id,
                **_export_simple_fields(alert, WHISKY_ALERT_FIELDS),
            }
            for alert in WhiskyDrinkingWindowAlert.objects.filter(
                household=household
            ).order_by("pk")
        ],
        "reorder_reminders": [
            {
                "backup_id": reminder.pk,
                "whisky": reminder.whisky_id,
                **_export_simple_fields(reminder, WHISKY_REMINDER_FIELDS),
            }
            for reminder in WhiskyReorderReminder.objects.filter(
                household=household
            ).order_by("pk")
        ],
        "price_history": [
            {
                "backup_id": record.pk,
                "whisky": record.whisky_id,
                "source": record.source_id,
                **_export_simple_fields(record, WHISKY_PRICE_HISTORY_FIELDS),
            }
            for record in WhiskyPriceHistory.objects.filter(
                household=household
            ).order_by("pk")
        ],
        "move_history": _export_move_histories(
            WhiskyBottleMoveHistory.objects.filter(
                storage_item__household=household
            ).select_related("storage_item", "from_storage", "to_storage")
        ),
    }


def _restore_settings(payload: dict, *, user, household) -> None:
    from wine_cellar.apps.household.models import HouseholdSettings
    from wine_cellar.apps.user.models import UserSettings

    user_settings, _ = UserSettings.objects.get_or_create(user=user)
    for field_name, value in _build_field_values(
        UserSettings,
        payload.get("user_settings") or {},
        USER_SETTINGS_FIELDS,
    ).items():
        setattr(user_settings, field_name, value)
    user_settings.active_household = household
    user_settings.save()

    household_settings, _ = HouseholdSettings.objects.get_or_create(household=household)
    for field_name, value in _build_field_values(
        HouseholdSettings,
        payload.get("household_settings") or {},
        HOUSEHOLD_SETTINGS_FIELDS,
    ).items():
        setattr(household_settings, field_name, value)
    household_settings.save()

    household_name = (payload.get("household") or {}).get("name")
    if household_name:
        household.name = household_name
        household.save(update_fields=["name"])


def _restore_wine_backup(data: dict, *, user, household) -> dict:
    from wine_cellar.apps.storage.models import BottleMoveHistory, Storage, StorageItem
    from wine_cellar.apps.wine.models import (
        Appellation,
        Attribute,
        BottleNote,
        Collection,
        DrinkingWindowAlert,
        DrinkRecord,
        FoodPairing,
        Grape,
        PriceHistory,
        ReorderReminder,
        Size,
        Source,
        Vineyard,
        Wine,
        WineBarcode,
        WineImage,
        Wishlist,
    )

    Collection.objects.filter(household=household).delete()
    Wishlist.objects.filter(household=household).delete()
    Wine.objects.filter(household=household).delete()
    Storage.objects.filter(household=household, app_type="wine").delete()
    Size.objects.filter(household=household).delete()
    Grape.objects.filter(household=household).delete()
    Attribute.objects.filter(household=household).delete()
    FoodPairing.objects.filter(household=household).delete()
    Vineyard.objects.filter(household=household).delete()
    Source.objects.filter(household=household).delete()

    storage_map = {}
    for storage_payload in data.get("storages", []):
        storage = Storage.objects.create(
            user=user,
            household=household,
            app_type="wine",
            **_build_field_values(Storage, storage_payload, STORAGE_FIELDS),
        )
        _restore_timestamps(storage, storage_payload, ["created", "modified"])
        storage_map[storage_payload["backup_id"]] = storage

    refs = data.get("references", {})
    size_map = _restore_reference_items(
        items=refs.get("sizes", []),
        model_class=Size,
        user=user,
        household=household,
        fields=WINE_REFERENCE_FIELDS["sizes"],
    )
    grape_map = _restore_reference_items(
        items=refs.get("grapes", []),
        model_class=Grape,
        user=user,
        household=household,
        fields=WINE_REFERENCE_FIELDS["grapes"],
    )
    attribute_map = _restore_reference_items(
        items=refs.get("attributes", []),
        model_class=Attribute,
        user=user,
        household=household,
        fields=WINE_REFERENCE_FIELDS["attributes"],
    )
    pairing_map = _restore_reference_items(
        items=refs.get("food_pairings", []),
        model_class=FoodPairing,
        user=user,
        household=household,
        fields=WINE_REFERENCE_FIELDS["food_pairings"],
    )
    vineyard_map = _restore_reference_items(
        items=refs.get("vineyards", []),
        model_class=Vineyard,
        user=user,
        household=household,
        fields=WINE_REFERENCE_FIELDS["vineyards"],
    )
    source_map = _restore_reference_items(
        items=refs.get("sources", []),
        model_class=Source,
        user=user,
        household=household,
        fields=WINE_REFERENCE_FIELDS["sources"],
    )

    wine_map = {}
    for wine_payload in data.get("wines", []):
        appellation_payload = wine_payload.get("appellation")
        appellation = None
        if appellation_payload:
            appellation, _ = Appellation.objects.get_or_create(
                name=appellation_payload["name"],
                country=appellation_payload["country"],
                defaults={
                    "latitude": appellation_payload.get("latitude") or 0,
                    "longitude": appellation_payload.get("longitude") or 0,
                },
            )

        wine = Wine.objects.create(
            user=user,
            household=household,
            size=_require_mapping(size_map, wine_payload.get("size"), "size"),
            appellation=appellation,
            **_build_field_values(Wine, wine_payload, WINE_FIELDS),
        )
        wine.grapes.set(
            _require_many(grape_map, wine_payload.get("grapes", []), "grape")
        )
        wine.attributes.set(
            _require_many(
                attribute_map, wine_payload.get("attributes", []), "attribute"
            )
        )
        wine.food_pairings.set(
            _require_many(
                pairing_map,
                wine_payload.get("food_pairings", []),
                "food pairing",
            )
        )
        wine.vineyard.set(
            _require_many(vineyard_map, wine_payload.get("vineyard", []), "vineyard")
        )
        wine.source.set(
            _require_many(source_map, wine_payload.get("source", []), "source")
        )
        _restore_timestamps(wine, wine_payload, ["created", "modified"])
        wine_map[wine_payload["backup_id"]] = wine

        for barcode_payload in wine_payload.get("barcodes", []):
            barcode = WineBarcode.objects.create(
                wine=wine,
                user=user,
                household=household,
                barcode=barcode_payload["barcode"],
            )
            _restore_timestamps(barcode, barcode_payload, ["created"])

        for image_payload in wine_payload.get("images", []):
            image = WineImage(
                wine=wine,
                user=user,
                image_type=image_payload["image_type"],
                is_primary=image_payload["is_primary"],
            )
            _restore_file(image.image, image_payload.get("image"))
            _restore_file(image.thumbnail, image_payload.get("thumbnail"))
            image.save()

    for collection_payload in data.get("collections", []):
        collection = Collection.objects.create(
            user=user,
            household=household,
            **_build_field_values(Collection, collection_payload, COLLECTION_FIELDS),
        )
        collection.wines.set(
            _require_many(wine_map, collection_payload.get("wines", []), "wine")
        )
        _restore_timestamps(collection, collection_payload, ["created", "modified"])

    storage_item_map = {}
    for item_payload in data.get("storage_items", []):
        item = StorageItem.objects.create(
            user=user,
            household=household,
            storage=_require_mapping(storage_map, item_payload["storage"], "storage"),
            wine=_require_mapping(wine_map, item_payload["wine"], "wine"),
            **_build_field_values(StorageItem, item_payload, WINE_STORAGE_ITEM_FIELDS),
        )
        _restore_timestamps(item, item_payload, ["created", "modified"])
        storage_item_map[item_payload["backup_id"]] = item

    for wishlist_payload in data.get("wishlists", []):
        wishlist = Wishlist.objects.create(
            user=user,
            household=household,
            **_build_field_values(Wishlist, wishlist_payload, WINE_WISHLIST_FIELDS),
        )
        _restore_timestamps(wishlist, wishlist_payload, ["created", "modified"])

    for note_payload in data.get("bottle_notes", []):
        note = BottleNote.objects.create(
            user=user,
            household=household,
            storage_item=_require_mapping(
                storage_item_map,
                note_payload["storage_item"],
                "storage item",
            ),
            **_build_field_values(BottleNote, note_payload, WINE_BOTTLE_NOTE_FIELDS),
        )
        _restore_timestamps(note, note_payload, ["created", "modified"])

    for record_payload in data.get("drink_records", []):
        record = DrinkRecord.objects.create(
            user=user,
            household=household,
            wine=_require_mapping(wine_map, record_payload["wine"], "wine"),
            storage_item=_require_mapping(
                storage_item_map,
                record_payload.get("storage_item"),
                "storage item",
            ),
            **_build_field_values(
                DrinkRecord,
                record_payload,
                WINE_DRINK_RECORD_FIELDS,
            ),
        )
        _restore_timestamps(record, record_payload, ["created", "modified"])

    for alert_payload in data.get("alerts", []):
        alert = DrinkingWindowAlert.objects.create(
            user=user,
            household=household,
            wine=_require_mapping(wine_map, alert_payload["wine"], "wine"),
            **_build_field_values(
                DrinkingWindowAlert,
                alert_payload,
                WINE_ALERT_FIELDS,
            ),
        )
        _restore_timestamps(alert, alert_payload, ["created", "modified"])

    for reminder_payload in data.get("reorder_reminders", []):
        reminder = ReorderReminder.objects.create(
            user=user,
            household=household,
            wine=_require_mapping(wine_map, reminder_payload["wine"], "wine"),
            **_build_field_values(
                ReorderReminder,
                reminder_payload,
                WINE_REMINDER_FIELDS,
            ),
        )
        _restore_timestamps(reminder, reminder_payload, ["created", "modified"])

    for price_payload in data.get("price_history", []):
        record = PriceHistory.objects.create(
            user=user,
            household=household,
            wine=_require_mapping(wine_map, price_payload["wine"], "wine"),
            source=_require_mapping(source_map, price_payload.get("source"), "source"),
            **_build_field_values(PriceHistory, price_payload, ["price"]),
        )
        _restore_timestamps(record, price_payload, ["recorded_at"])

    for history_payload in data.get("move_history", []):
        history = BottleMoveHistory.objects.create(
            user=user,
            storage_item=_require_mapping(
                storage_item_map,
                history_payload["storage_item"],
                "storage item",
            ),
            from_storage=_require_mapping(
                storage_map,
                history_payload.get("from_storage"),
                "storage",
            ),
            to_storage=_require_mapping(
                storage_map,
                history_payload.get("to_storage"),
                "storage",
            ),
            **_build_field_values(
                BottleMoveHistory, history_payload, MOVE_HISTORY_FIELDS
            ),
        )
        _restore_timestamps(history, history_payload, ["moved_at"])

    return {
        "app_type": "wine",
        "beverages": len(wine_map),
        "storages": len(storage_map),
        "bottles": len(storage_item_map),
    }


def _restore_whisky_backup(data: dict, *, user, household) -> dict:
    from wine_cellar.apps.storage.models import Storage
    from wine_cellar.apps.whisky.models import (
        Bottler,
        CaskHistory,
        Collection,
        Distillery,
        Whisky,
        WhiskyAttribute,
        WhiskyBarcode,
        WhiskyBottleMoveHistory,
        WhiskyBottleNote,
        WhiskyDrinkingWindowAlert,
        WhiskyDrinkRecord,
        WhiskyImage,
        WhiskyPriceHistory,
        WhiskyRegion,
        WhiskyReorderReminder,
        WhiskySource,
        WhiskyStorageItem,
        WhiskyWishlist,
    )

    Collection.objects.filter(household=household).delete()
    WhiskyWishlist.objects.filter(household=household).delete()
    Whisky.objects.filter(household=household).delete()
    Storage.objects.filter(household=household, app_type="whisky").delete()
    WhiskyAttribute.objects.filter(household=household).delete()
    WhiskySource.objects.filter(household=household).delete()

    storage_map = {}
    for storage_payload in data.get("storages", []):
        storage = Storage.objects.create(
            user=user,
            household=household,
            app_type="whisky",
            **_build_field_values(Storage, storage_payload, STORAGE_FIELDS),
        )
        _restore_timestamps(storage, storage_payload, ["created", "modified"])
        storage_map[storage_payload["backup_id"]] = storage

    refs = data.get("references", {})
    attribute_map = _restore_reference_items(
        items=refs.get("attributes", []),
        model_class=WhiskyAttribute,
        user=user,
        household=household,
        fields=WHISKY_REFERENCE_FIELDS["attributes"],
    )
    source_map = _restore_reference_items(
        items=refs.get("sources", []),
        model_class=WhiskySource,
        user=user,
        household=household,
        fields=WHISKY_REFERENCE_FIELDS["sources"],
    )
    region_map = {}
    for region_payload in refs.get("regions", []):
        region, _ = WhiskyRegion.objects.get_or_create(
            name=region_payload["name"],
            country=region_payload["country"],
            defaults=_build_field_values(
                WhiskyRegion,
                region_payload,
                [
                    "slug",
                    "latitude",
                    "longitude",
                    "description",
                    "order",
                ],
            ),
        )
        region_map[region_payload["backup_id"]] = region

    distillery_map = {}
    for distillery_payload in refs.get("distilleries", []):
        distillery, _ = Distillery.objects.get_or_create(
            name=distillery_payload["name"],
            country=distillery_payload["country"],
            defaults={
                **_build_field_values(
                    Distillery,
                    distillery_payload,
                    [
                        "latitude",
                        "longitude",
                        "status",
                        "founded_year",
                        "closed_year",
                        "owner",
                        "description",
                        "is_user_created",
                    ],
                ),
                "region": region_map.get(distillery_payload.get("region")),
            },
        )
        if distillery.region_id is None and distillery_payload.get("region"):
            distillery.region = region_map.get(distillery_payload.get("region"))
            distillery.save(update_fields=["region"])
        distillery_map[distillery_payload["backup_id"]] = distillery

    bottler_map = {}
    for bottler_payload in refs.get("bottlers", []):
        bottler, _ = Bottler.objects.get_or_create(
            name=bottler_payload["name"],
            country=bottler_payload["country"],
            defaults=_build_field_values(
                Bottler,
                bottler_payload,
                [
                    "short_name",
                    "website",
                    "description",
                    "is_user_created",
                ],
            ),
        )
        bottler_map[bottler_payload["backup_id"]] = bottler

    whisky_map = {}
    for whisky_payload in data.get("whiskies", []):
        whisky = Whisky.objects.create(
            user=user,
            household=household,
            region=_require_mapping(region_map, whisky_payload.get("region"), "region"),
            distillery=_require_mapping(
                distillery_map,
                whisky_payload.get("distillery"),
                "distillery",
            ),
            bottler=_require_mapping(
                bottler_map,
                whisky_payload.get("bottler"),
                "bottler",
            ),
            source=_require_mapping(source_map, whisky_payload.get("source"), "source"),
            **_build_field_values(Whisky, whisky_payload, WHISKY_FIELDS),
        )
        whisky.attributes.set(
            _require_many(
                attribute_map,
                whisky_payload.get("attributes", []),
                "attribute",
            )
        )
        _restore_timestamps(whisky, whisky_payload, ["created", "modified"])
        whisky_map[whisky_payload["backup_id"]] = whisky

        for barcode_payload in whisky_payload.get("barcodes", []):
            barcode = WhiskyBarcode.objects.create(
                whisky=whisky,
                user=user,
                household=household,
                barcode=barcode_payload["barcode"],
            )
            _restore_timestamps(barcode, barcode_payload, ["created"])

        for image_payload in whisky_payload.get("images", []):
            image = WhiskyImage(
                whisky=whisky,
                user=user,
                image_type=image_payload["image_type"],
                is_primary=image_payload["is_primary"],
            )
            _restore_file(image.image, image_payload.get("image"))
            _restore_file(image.thumbnail, image_payload.get("thumbnail"))
            image.save()
            _restore_timestamps(image, image_payload, ["created"])

        for cask_payload in whisky_payload.get("cask_history", []):
            CaskHistory.objects.create(
                whisky=whisky,
                **_build_field_values(
                    CaskHistory, cask_payload, WHISKY_CASK_HISTORY_FIELDS
                ),
            )

    for collection_payload in data.get("collections", []):
        collection = Collection.objects.create(
            user=user,
            household=household,
            **_build_field_values(Collection, collection_payload, COLLECTION_FIELDS),
        )
        collection.whiskies.set(
            _require_many(
                whisky_map,
                collection_payload.get("whiskies", []),
                "whisky",
            )
        )
        _restore_timestamps(collection, collection_payload, ["created", "modified"])

    storage_item_map = {}
    for item_payload in data.get("storage_items", []):
        item = WhiskyStorageItem.objects.create(
            user=user,
            household=household,
            storage=_require_mapping(storage_map, item_payload["storage"], "storage"),
            whisky=_require_mapping(whisky_map, item_payload["whisky"], "whisky"),
            **_build_field_values(
                WhiskyStorageItem,
                item_payload,
                WHISKY_STORAGE_ITEM_FIELDS,
            ),
        )
        _restore_timestamps(item, item_payload, ["created", "modified"])
        storage_item_map[item_payload["backup_id"]] = item

    for wishlist_payload in data.get("wishlists", []):
        wishlist = WhiskyWishlist.objects.create(
            user=user,
            household=household,
            region=_require_mapping(
                region_map,
                wishlist_payload.get("region"),
                "region",
            ),
            distillery=_require_mapping(
                distillery_map,
                wishlist_payload.get("distillery"),
                "distillery",
            ),
            **_build_field_values(
                WhiskyWishlist,
                wishlist_payload,
                WHISKY_WISHLIST_FIELDS,
            ),
        )
        _restore_timestamps(wishlist, wishlist_payload, ["created", "modified"])

    for note_payload in data.get("bottle_notes", []):
        note = WhiskyBottleNote.objects.create(
            user=user,
            household=household,
            storage_item=_require_mapping(
                storage_item_map,
                note_payload["storage_item"],
                "storage item",
            ),
            **_build_field_values(
                WhiskyBottleNote,
                note_payload,
                WHISKY_BOTTLE_NOTE_FIELDS,
            ),
        )
        _restore_timestamps(note, note_payload, ["created", "modified"])

    for record_payload in data.get("drink_records", []):
        record = WhiskyDrinkRecord.objects.create(
            user=user,
            household=household,
            whisky=_require_mapping(whisky_map, record_payload["whisky"], "whisky"),
            storage_item=_require_mapping(
                storage_item_map,
                record_payload.get("storage_item"),
                "storage item",
            ),
            **_build_field_values(
                WhiskyDrinkRecord,
                record_payload,
                WHISKY_DRINK_RECORD_FIELDS,
            ),
        )
        _restore_timestamps(record, record_payload, ["created", "modified"])

    for alert_payload in data.get("alerts", []):
        alert = WhiskyDrinkingWindowAlert.objects.create(
            user=user,
            household=household,
            whisky=_require_mapping(whisky_map, alert_payload["whisky"], "whisky"),
            **_build_field_values(
                WhiskyDrinkingWindowAlert,
                alert_payload,
                WHISKY_ALERT_FIELDS,
            ),
        )
        _restore_timestamps(alert, alert_payload, ["created", "modified"])

    for reminder_payload in data.get("reorder_reminders", []):
        reminder = WhiskyReorderReminder.objects.create(
            user=user,
            household=household,
            whisky=_require_mapping(whisky_map, reminder_payload["whisky"], "whisky"),
            **_build_field_values(
                WhiskyReorderReminder,
                reminder_payload,
                WHISKY_REMINDER_FIELDS,
            ),
        )
        _restore_timestamps(reminder, reminder_payload, ["created", "modified"])

    for price_payload in data.get("price_history", []):
        record = WhiskyPriceHistory.objects.create(
            user=user,
            household=household,
            whisky=_require_mapping(whisky_map, price_payload["whisky"], "whisky"),
            source=_require_mapping(source_map, price_payload.get("source"), "source"),
            **_build_field_values(WhiskyPriceHistory, price_payload, ["price"]),
        )
        _restore_timestamps(record, price_payload, ["recorded_at"])

    for history_payload in data.get("move_history", []):
        history = WhiskyBottleMoveHistory.objects.create(
            user=user,
            storage_item=_require_mapping(
                storage_item_map,
                history_payload["storage_item"],
                "storage item",
            ),
            from_storage=_require_mapping(
                storage_map,
                history_payload.get("from_storage"),
                "storage",
            ),
            to_storage=_require_mapping(
                storage_map,
                history_payload.get("to_storage"),
                "storage",
            ),
            **_build_field_values(
                WhiskyBottleMoveHistory,
                history_payload,
                MOVE_HISTORY_FIELDS,
            ),
        )
        _restore_timestamps(history, history_payload, ["moved_at"])

    return {
        "app_type": "whisky",
        "beverages": len(whisky_map),
        "storages": len(storage_map),
        "bottles": len(storage_item_map),
    }


def _restore_reference_items(*, items, model_class, user, household, fields):
    restored = {}
    for item_payload in items:
        obj = model_class.objects.create(
            user=user,
            household=household,
            **_build_field_values(model_class, item_payload, fields),
        )
        _restore_timestamps(obj, item_payload, ["created", "modified"])
        restored[item_payload["backup_id"]] = obj
    return restored
