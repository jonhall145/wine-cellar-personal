import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from wine_cellar.apps.storage.models import BottleMoveHistory, Storage, StorageItem
from wine_cellar.apps.user.backup import (
    _restore_reference_items,
    _restore_wine_backup,
)
from wine_cellar.apps.wine.models import (
    BottleNote,
    Collection,
    DrinkingWindowAlert,
    DrinkRecord,
    PriceHistory,
    ReorderReminder,
    Size,
    Wine,
    WineImage,
    Wishlist,
)


@pytest.mark.django_db
def test_backup_export_includes_structured_wine_data(
    client,
    user,
    wine_factory,
    grape_factory,
    attribute_factory,
    food_pairing_factory,
    vineyard_factory,
    source_factory,
    size_factory,
    storage_factory,
    storage_item_factory,
    wine_image_factory,
    clear_image_folder,
):
    household = user.user_settings.active_household
    grape = grape_factory(user=user, household=household, name="Riesling")
    attribute = attribute_factory(user=user, household=household, name="Mineral")
    pairing = food_pairing_factory(user=user, household=household, name="Fish")
    vineyard = vineyard_factory(user=user, household=household, name="Estate")
    source = source_factory(user=user, household=household, name="Merchant")
    size = size_factory(user=user, household=household)
    wine = wine_factory(
        user=user,
        household=household,
        name="Backup Riesling",
        size=size,
        grapes=[grape],
    )
    wine.attributes.add(attribute)
    wine.food_pairings.add(pairing)
    wine.vineyard.add(vineyard)
    wine.source.add(source)
    storage = storage_factory(user=user, household=household, name="Rack A")
    destination = storage_factory(user=user, household=household, name="Rack B")
    item = storage_item_factory(
        user=user,
        household=household,
        wine=wine,
        storage=storage,
        row=1,
        column=2,
    )
    BottleNote.objects.create(
        user=user,
        household=household,
        storage_item=item,
        note_date="2024-02-03",
        note="Holding well",
    )
    DrinkRecord.objects.create(
        user=user,
        household=household,
        wine=wine,
        storage_item=item,
        date_consumed="2024-03-04",
        tasting_notes="Citrus",
    )
    DrinkingWindowAlert.objects.create(
        user=user,
        household=household,
        wine=wine,
        alert_date="2024-01-05",
        message="Drink soon",
    )
    ReorderReminder.objects.create(
        user=user,
        household=household,
        wine=wine,
        min_stock=2,
    )
    wishlist = Wishlist.objects.create(
        user=user,
        household=household,
        name="Wishlist Wine",
    )
    collection = Collection.objects.create(
        user=user,
        household=household,
        name="Favorites",
    )
    collection.wines.add(wine)
    PriceHistory.objects.create(
        user=user,
        household=household,
        wine=wine,
        source=source,
        price="19.95",
    )
    BottleMoveHistory.objects.create(
        user=user,
        storage_item=item,
        from_storage=storage,
        from_row=1,
        from_column=2,
        to_storage=destination,
        to_row=2,
        to_column=1,
    )
    wine.barcodes.create(user=user, household=household, barcode="1234567890123")
    wine_image_factory(wine=wine, user=user)

    client.force_login(user)
    response = client.get(reverse("user-backup-export"))

    assert response.status_code == 200
    payload = json.loads(response.content)
    assert payload["app_type"] == "wine"
    assert payload["data"]["wines"][0]["name"] == "Backup Riesling"
    assert payload["data"]["wines"][0]["images"][0]["image"]["data"]
    assert payload["data"]["collections"][0]["wines"] == [wine.pk]
    assert payload["data"]["wishlists"][0]["name"] == wishlist.name
    assert payload["data"]["move_history"][0]["to_storage"] == destination.pk


@pytest.mark.django_db
def test_backup_restore_replaces_current_wine_household_data(
    client,
    user,
    wine_factory,
    source_factory,
    storage_factory,
    storage_item_factory,
    wine_image_factory,
    clear_image_folder,
):
    household = user.user_settings.active_household
    source = source_factory(user=user, household=household, name="Importer")
    wine = wine_factory(user=user, household=household, name="Restored Wine")
    storage = storage_factory(user=user, household=household, name="Rack A")
    item = storage_item_factory(
        user=user,
        household=household,
        wine=wine,
        storage=storage,
    )
    BottleNote.objects.create(
        user=user,
        household=household,
        storage_item=item,
        note_date="2024-04-05",
        note="From backup",
    )
    DrinkRecord.objects.create(
        user=user,
        household=household,
        wine=wine,
        storage_item=item,
        date_consumed="2024-04-06",
    )
    PriceHistory.objects.create(
        user=user,
        household=household,
        wine=wine,
        source=source,
        price="21.50",
    )
    collection = Collection.objects.create(
        user=user,
        household=household,
        name="Restored Collection",
    )
    collection.wines.add(wine)
    wine_image_factory(wine=wine, user=user)

    client.force_login(user)
    export_response = client.get(reverse("user-backup-export"))

    replacement_storage = storage_factory(
        user=user,
        household=household,
        name="Temporary Rack",
    )
    replacement_wine = wine_factory(
        user=user,
        household=household,
        name="Temporary Wine",
    )
    storage_item_factory(
        user=user,
        household=household,
        wine=replacement_wine,
        storage=replacement_storage,
    )

    upload = SimpleUploadedFile(
        "wine-backup.json",
        export_response.content,
        content_type="application/json",
    )
    response = client.post(
        reverse("user-backup-import"),
        {"backup_file": upload, "confirm_replace": "on"},
        follow=True,
    )

    assert response.status_code == 200
    assert b"Backup restored:" in response.content
    assert list(
        Wine.objects.filter(household=household).values_list("name", flat=True)
    ) == ["Restored Wine"]
    assert set(
        Storage.objects.filter(household=household, app_type="wine").values_list(
            "name",
            flat=True,
        )
    ) == {"Default Shelf", "Rack A"}
    assert BottleNote.objects.filter(household=household, note="From backup").exists()
    assert DrinkRecord.objects.filter(
        household=household, wine__name="Restored Wine"
    ).exists()
    assert Collection.objects.filter(
        household=household, name="Restored Collection"
    ).exists()
    assert WineImage.objects.filter(wine__household=household).count() == 1


@pytest.mark.django_db
def test_backup_restore_maps_legacy_half_and_standard_size_ids_to_one_size(
    user, household_factory
):
    household = user.user_settings.active_household
    Size.objects.create(
        name="ST",
        user=user,
        household=household_factory(),
    )
    size_map = _restore_reference_items(
        items=[
            {"backup_id": 101, "name": "HA"},
            {"backup_id": 202, "name": "ST"},
        ],
        model_class=Size,
        user=user,
        household=household,
        fields=["name"],
    )

    assert size_map[101].pk == size_map[202].pk
    assert size_map[101].name == "ST"
    assert (
        Size.objects.filter(
            user=None,
            household=household,
            name="ST",
        ).count()
        == 1
    )
    assert Size.objects.filter(user=user, name="ST").count() == 1


@pytest.mark.django_db
def test_backup_restore_keeps_both_wines_when_legacy_sizes_normalize_to_standard(user):
    household = user.user_settings.active_household
    data = {
        "storages": [{"backup_id": 1, "name": "Cellar", "location": "Home"}],
        "references": {
            "sizes": [
                {"backup_id": 101, "name": "HA"},
                {"backup_id": 202, "name": "ST"},
            ],
            "grapes": [],
            "attributes": [],
            "food_pairings": [],
            "vineyards": [],
            "sources": [],
        },
        "wines": [
            {
                "backup_id": 11,
                "name": "Same wine",
                "wine_type": "RE",
                "abv": 12.5,
                "vintage": 2019,
                "country": "FR",
                "size": 101,
                "deleted": False,
                "grapes": [],
                "attributes": [],
                "food_pairings": [],
                "vineyard": [],
                "source": [],
            },
            {
                "backup_id": 22,
                "name": "Same wine",
                "wine_type": "RE",
                "abv": 12.5,
                "vintage": 2019,
                "country": "FR",
                "size": 202,
                "deleted": False,
                "grapes": [],
                "attributes": [],
                "food_pairings": [],
                "vineyard": [],
                "source": [],
            },
        ],
        "storage_items": [
            {"backup_id": 301, "storage": 1, "wine": 11, "row": 1, "column": 1},
            {"backup_id": 302, "storage": 1, "wine": 22, "row": 1, "column": 2},
        ],
        "bottle_notes": [
            {
                "backup_id": 401,
                "storage_item": 301,
                "note_date": "2024-01-02",
                "note": "Legacy half-size bottle",
            },
            {
                "backup_id": 402,
                "storage_item": 302,
                "note_date": "2024-01-03",
                "note": "Standard bottle",
            },
        ],
        "drink_records": [
            {
                "backup_id": 501,
                "wine": 11,
                "storage_item": 301,
                "date_consumed": "2024-02-01",
                "tasting_notes": "Half-size history",
            },
            {
                "backup_id": 502,
                "wine": 22,
                "storage_item": 302,
                "date_consumed": "2024-02-02",
                "tasting_notes": "Standard history",
            },
        ],
    }

    result = _restore_wine_backup(data, user=user, household=household)

    wines = list(Wine.objects.filter(household=household).order_by("pk"))
    assert result["beverages"] == 2
    assert len(wines) == 2
    assert {wine.name for wine in wines} == {"Same wine"}
    assert all(wine.size.name == "ST" for wine in wines)
    assert len({wine.size_id for wine in wines}) == 2
    assert StorageItem.objects.filter(household=household).count() == 2
    assert (
        StorageItem.objects.filter(household=household)
        .values_list("wine_id", flat=True)
        .distinct()
        .count()
        == 2
    )
    assert not Size.objects.filter(household=household, name="HA").exists()
    assert set(
        BottleNote.objects.filter(household=household).values_list("note", flat=True)
    ) == {"Legacy half-size bottle", "Standard bottle"}
    assert set(
        DrinkRecord.objects.filter(household=household).values_list(
            "tasting_notes", flat=True
        )
    ) == {"Half-size history", "Standard history"}
