import os
import shutil
from pathlib import Path

import pytest
from django.conf import settings
from pytest_factoryboy import register

from wine_cellar.apps.household.tests.factories import (
    HouseholdFactory,
    HouseholdMembershipFactory,
    HouseholdSettingsFactory,
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
    WineBarcodeFactory,
    WineFactory,
    WineImageFactory,
)

# Skip whisky tests when not running in whisky mode
collect_ignore_glob = []
if os.environ.get("CELLAR_APP_TYPE") != "whisky":
    collect_ignore_glob.append("whisky/*")

register(UserFactory)
register(HouseholdFactory)
register(HouseholdMembershipFactory)
register(HouseholdSettingsFactory)
register(WineFactory)
register(WineBarcodeFactory)
register(GrapeFactory)
register(WineImageFactory)
register(VineyardFactory)
register(FoodPairingFactory)
register(AttributeFactory)
register(SizeFactory)
register(SourceFactory)
register(StorageFactory)
register(StorageItemFactory)


@pytest.fixture(autouse=True)
def _simple_static_storage(settings):
    """Use simple static storage in tests — no collectstatic manifest required.

    When running via `make pytest` (Docker), the env var DJANGO_SETTINGS_MODULE
    points to docker_settings which uses GzipOnlyManifestStaticFilesStorage.
    That requires a prior collectstatic + webpack build, causing all view tests
    to fail with 'Missing staticfiles manifest'. This fixture ensures tests
    always use the plain StaticFilesStorage backend.
    """
    settings.STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }


@pytest.fixture
def clear_image_folder():
    yield
    path = Path(settings.MEDIA_ROOT)
    if path.exists():
        for child in path.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
