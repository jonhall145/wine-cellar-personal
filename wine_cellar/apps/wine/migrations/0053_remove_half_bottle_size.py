from django.db import migrations, models

WINE_IDENTITY_FIELDS = (
    "name",
    "wine_type",
    "abv",
    "vintage",
    "country",
    "user_id",
)


def _find_standard_size(Size, half_size):
    candidates = Size.objects.filter(
        name="ST",
        household_id=half_size.household_id,
    )
    if half_size.user_id is not None:
        same_owner = candidates.filter(user_id=half_size.user_id).order_by("pk").first()
        if same_owner:
            return same_owner

    shared_size = candidates.filter(user_id__isnull=True).order_by("pk").first()
    if shared_size:
        return shared_size

    return candidates.order_by("pk").first()


def _merge_wine(apps, duplicate, survivor):
    """Move inventory and history to the equivalent Standard-size wine."""
    StorageItem = apps.get_model("storage", "StorageItem")
    WineImage = apps.get_model("wine", "WineImage")
    WineBarcode = apps.get_model("wine", "WineBarcode")
    DrinkRecord = apps.get_model("wine", "DrinkRecord")
    DrinkingWindowAlert = apps.get_model("wine", "DrinkingWindowAlert")
    ReorderReminder = apps.get_model("wine", "ReorderReminder")
    PriceHistory = apps.get_model("wine", "PriceHistory")
    Collection = apps.get_model("wine", "Collection")

    for relation in ("grapes", "attributes", "food_pairings", "vineyard", "source"):
        related_ids = getattr(duplicate, relation).values_list("pk", flat=True)
        getattr(survivor, relation).add(*related_ids)

    if not survivor.appellation_id and duplicate.appellation_id:
        survivor.appellation_id = duplicate.appellation_id
        survivor.save(update_fields=["appellation"])

    StorageItem.objects.filter(wine_id=duplicate.pk).update(wine_id=survivor.pk)
    DrinkRecord.objects.filter(wine_id=duplicate.pk).update(wine_id=survivor.pk)
    DrinkingWindowAlert.objects.filter(wine_id=duplicate.pk).update(wine_id=survivor.pk)
    PriceHistory.objects.filter(wine_id=duplicate.pk).update(wine_id=survivor.pk)
    apps.get_model("wine", "VisionExtractionLog").objects.filter(
        wine_id=duplicate.pk
    ).update(wine_id=survivor.pk)

    survivor_has_primary = WineImage.objects.filter(
        wine_id=survivor.pk,
        is_primary=True,
    ).exists()
    if survivor_has_primary:
        WineImage.objects.filter(
            wine_id=duplicate.pk,
            is_primary=True,
        ).update(is_primary=False)
    WineImage.objects.filter(wine_id=duplicate.pk).update(wine_id=survivor.pk)

    for barcode in WineBarcode.objects.filter(wine_id=duplicate.pk):
        if (
            WineBarcode.objects.filter(
                barcode=barcode.barcode,
                user_id=barcode.user_id,
                wine_id=survivor.pk,
            )
            .exclude(pk=barcode.pk)
            .exists()
        ):
            barcode.delete()
        else:
            WineBarcode.objects.filter(pk=barcode.pk).update(wine_id=survivor.pk)

    for reminder in ReorderReminder.objects.filter(wine_id=duplicate.pk):
        existing = (
            ReorderReminder.objects.filter(
                wine_id=survivor.pk,
                user_id=reminder.user_id,
            )
            .exclude(pk=reminder.pk)
            .first()
        )
        if existing:
            existing.min_stock = max(existing.min_stock, reminder.min_stock)
            existing.is_active = existing.is_active or reminder.is_active
            existing.save(update_fields=["min_stock", "is_active"])
            reminder.delete()
        else:
            ReorderReminder.objects.filter(pk=reminder.pk).update(wine_id=survivor.pk)

    for collection in Collection.objects.filter(wines=duplicate).distinct():
        collection.wines.add(survivor)

    duplicate.delete()


def _merge_size_collisions(apps, Wine, half_size, standard_size):
    active_half_wines = Wine.objects.filter(
        size_id=half_size.pk,
        deleted=False,
    ).order_by("pk")
    for half_wine in active_half_wines.iterator():
        # The unique constraint uses the database's default NULL-distinct
        # behavior, so rows with any nullable key part cannot collide.
        if any(
            getattr(half_wine, field) is None for field in ("abv", "vintage", "user_id")
        ):
            continue
        identity = {field: getattr(half_wine, field) for field in WINE_IDENTITY_FIELDS}
        standard_wine = (
            Wine.objects.filter(
                size_id=standard_size.pk,
                deleted=False,
                **identity,
            )
            .order_by("pk")
            .first()
        )
        if standard_wine:
            _merge_wine(apps, half_wine, standard_wine)


def replace_half_bottle_sizes(apps, schema_editor):
    Size = apps.get_model("wine", "Size")
    Wine = apps.get_model("wine", "Wine")

    for half_size in Size.objects.filter(name="HA").iterator():
        standard_size = _find_standard_size(Size, half_size)
        if standard_size:
            _merge_size_collisions(apps, Wine, half_size, standard_size)
            Wine.objects.filter(size_id=half_size.pk).update(size_id=standard_size.pk)
            half_size.delete()
        else:
            # Keep the new standard size in the same household. The user-based
            # uniqueness constraint may already be occupied by another
            # household's Standard size, in which case make this a household
            # shared reference instead of borrowing that other household's row.
            if (
                half_size.user_id is not None
                and Size.objects.filter(
                    name="ST",
                    user_id=half_size.user_id,
                )
                .exclude(pk=half_size.pk)
                .exists()
            ):
                half_size.user_id = None
            half_size.name = "ST"
            half_size.save(update_fields=["name", "user"])


class Migration(migrations.Migration):
    dependencies = [
        ("wine", "0052_alter_visionextractionlog_model_used"),
    ]

    operations = [
        migrations.RunPython(replace_half_bottle_sizes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="size",
            name="name",
            field=models.CharField(
                choices=[
                    ("PI", "Piccolo (187ml)"),
                    ("DE", "Demi (375ml)"),
                    ("ST", "Standard (750ml)"),
                    ("LI", "Liter (1L)"),
                    ("MA", "Magnum (1.5L)"),
                    ("JE", "Jeroboam (3L)"),
                    ("RE", "Rehoboam (4.5L)"),
                ],
                default="ST",
                max_length=2,
                verbose_name="Size",
            ),
        ),
    ]
