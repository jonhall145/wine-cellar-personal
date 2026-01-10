import shutil
from pathlib import Path

import pytest
from django.conf import settings
from pytest_factoryboy import register

from wine_cellar.apps.hardware.tests.factories import (
    HardwareDeviceFactory,
    OfflineOperationFactory,
    PositionChangeReviewFactory,
    RackSnapshotFactory,
    RackVisionConfigFactory,
)
from wine_cellar.apps.storage.tests.factories import StorageFactory, StorageItemFactory
from wine_cellar.apps.user.tests.factories import UserFactory
from wine_cellar.apps.wine.tests.factories import (
    AttributeFactory,
    FoodPairingFactory,
    GrapeFactory,
    SizeFactory,
    SourceFactory,
    VineyardFactory,
    WineFactory,
    WineImageFactory,
)

register(UserFactory)
register(WineFactory)
register(GrapeFactory)
register(WineImageFactory)
register(VineyardFactory)
register(FoodPairingFactory)
register(AttributeFactory)
register(SizeFactory)
register(SourceFactory)
register(StorageFactory)
register(StorageItemFactory)

# Hardware factories
register(HardwareDeviceFactory)
register(PositionChangeReviewFactory)
register(RackSnapshotFactory)
register(OfflineOperationFactory)
register(RackVisionConfigFactory)


@pytest.fixture
def clear_image_folder():
    yield
    path = settings.BASE_DIR / Path("test_media")
    if path.exists():
        shutil.rmtree(path)
