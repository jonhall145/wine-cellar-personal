import base64
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from wine_cellar.apps.whisky.models import (
    CaskHistory,
    Collection,
    PreviousContents,
    WhiskyAttribute,
    WhiskyBottleNote,
    WhiskyDrinkRecord,
    WhiskyImage,
    WhiskyPriceHistory,
    WhiskyReorderReminder,
    WhiskySource,
    WhiskyWishlist,
)

VALID_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMC"
    "AO7Z0z0AAAAASUVORK5CYII="
)


@pytest.mark.django_db
def test_backup_export_and_restore_for_whisky_mode(
    client,
    user,
    whisky_factory,
    distillery_factory,
    bottler_factory,
    whisky_region_factory,
    storage_factory,
    whisky_storage_item_factory,
    clear_image_folder,
):
    household = user.user_settings.active_household
    region = whisky_region_factory(name="Islay", slug="islay")
    distillery = distillery_factory(name="Lagavulin", region=region)
    bottler = bottler_factory(name="Indie Bottler")
    source = WhiskySource.objects.create(user=user, household=household, name="Shop")
    attribute = WhiskyAttribute.objects.create(
        user=user,
        household=household,
        name="Smoky",
    )
    whisky = whisky_factory(
        user=user,
        household=household,
        name="Backup Whisky",
        region=region,
        distillery=distillery,
        bottler=bottler,
        source=source,
    )
    whisky.attributes.add(attribute)
    CaskHistory.objects.create(
        whisky=whisky,
        order=1,
        cask_type="Bourbon Barrel",
        previous_contents=PreviousContents.BOURBON,
    )
    storage = storage_factory(
        user=user,
        household=household,
        app_type="whisky",
        name="Whisky Rack",
    )
    item = whisky_storage_item_factory(
        user=user,
        household=household,
        whisky=whisky,
        storage=storage,
    )
    WhiskyBottleNote.objects.create(
        user=user,
        household=household,
        storage_item=item,
        note_date="2024-05-01",
        note="Smoky note",
    )
    WhiskyDrinkRecord.objects.create(
        user=user,
        household=household,
        whisky=whisky,
        storage_item=item,
        date_consumed="2024-05-02",
    )
    WhiskyPriceHistory.objects.create(
        user=user,
        household=household,
        whisky=whisky,
        source=source,
        price="99.99",
    )
    WhiskyWishlist.objects.create(
        user=user,
        household=household,
        name="Wishlist Whisky",
        distillery=distillery,
        region=region,
    )
    WhiskyReorderReminder.objects.create(
        user=user,
        household=household,
        whisky=whisky,
        min_stock=1,
    )
    collection = Collection.objects.create(
        user=user,
        household=household,
        name="Peat",
    )
    collection.whiskies.add(whisky)
    whisky.barcodes.create(user=user, household=household, barcode="5901234123457")
    WhiskyImage.objects.create(
        whisky=whisky,
        user=user,
        image=SimpleUploadedFile(
            "whisky.png",
            VALID_PNG_BYTES,
            content_type="image/png",
        ),
        image_type=WhiskyImage.ImageType.LABEL_FRONT,
        is_primary=True,
    )

    client.force_login(user)
    export_response = client.get(reverse("user-backup-export"))
    payload = json.loads(export_response.content)

    assert export_response.status_code == 200
    assert payload["app_type"] == "whisky"
    assert payload["data"]["whiskies"][0]["name"] == "Backup Whisky"
    assert (
        payload["data"]["whiskies"][0]["cask_history"][0]["cask_type"]
        == "Bourbon Barrel"
    )
    assert payload["data"]["collections"][0]["whiskies"] == [whisky.pk]

    replacement = whisky_factory(
        user=user, household=household, name="Temporary Whisky"
    )
    replacement.attributes.add(attribute)

    upload = SimpleUploadedFile(
        "whisky-backup.json",
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
        collection.__class__.objects.filter(household=household).values_list(
            "name",
            flat=True,
        )
    ) == ["Peat"]
    assert list(
        whisky.__class__.objects.filter(household=household).values_list(
            "name", flat=True
        )
    ) == ["Backup Whisky"]
    assert WhiskyBottleNote.objects.filter(
        household=household, note="Smoky note"
    ).exists()
    assert WhiskyDrinkRecord.objects.filter(
        household=household,
        whisky__name="Backup Whisky",
    ).exists()
    assert WhiskyImage.objects.filter(whisky__household=household).count() == 1
