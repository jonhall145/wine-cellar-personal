import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from wine_cellar.apps.storage.models import BottleMoveHistory, Storage
from wine_cellar.apps.wine.models import (
    BottleNote,
    Collection,
    DrinkingWindowAlert,
    DrinkRecord,
    PriceHistory,
    ReorderReminder,
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
