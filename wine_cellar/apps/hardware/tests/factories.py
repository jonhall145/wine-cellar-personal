"""Factory classes for hardware app tests."""

import secrets

import factory
from factory.django import DjangoModelFactory

from wine_cellar.apps.hardware.models import (
    HardwareDevice,
    PositionChangeReview,
    RackSnapshot,
    OfflineOperation,
    RackVisionConfig,
    ChangeType,
    ReviewStatus,
)
from wine_cellar.apps.storage.tests.factories import StorageFactory
from wine_cellar.apps.user.tests.factories import UserFactory
from wine_cellar.apps.wine.tests.factories import WineFactory


class HardwareDeviceFactory(DjangoModelFactory):
    class Meta:
        model = HardwareDevice

    user = factory.SubFactory(UserFactory)
    name = factory.Faker("word")
    device_id = factory.LazyFunction(lambda: f"pi-{secrets.token_hex(8)}")
    storage = factory.SubFactory(StorageFactory)
    api_token = factory.LazyFunction(lambda: secrets.token_urlsafe(32))
    is_active = True


class PositionChangeReviewFactory(DjangoModelFactory):
    class Meta:
        model = PositionChangeReview

    user = factory.SubFactory(UserFactory)
    storage = factory.SubFactory(StorageFactory)
    wine = factory.SubFactory(WineFactory)
    row = 1
    column = 1
    change_type = ChangeType.ADDED
    confidence = 0.85
    status = ReviewStatus.PENDING


class RackSnapshotFactory(DjangoModelFactory):
    class Meta:
        model = RackSnapshot

    user = factory.SubFactory(UserFactory)
    storage = factory.SubFactory(StorageFactory)
    grid_state = {"occupied": [[True, False], [False, True]]}


class OfflineOperationFactory(DjangoModelFactory):
    class Meta:
        model = OfflineOperation

    user = factory.SubFactory(UserFactory)
    device = factory.SubFactory(HardwareDeviceFactory)
    operation_type = "add_wine"
    operation_data = {"wine_id": 1, "rack_id": 1, "row": 1, "col": 1}
    client_timestamp = factory.Faker("date_time_this_year")


class RackVisionConfigFactory(DjangoModelFactory):
    class Meta:
        model = RackVisionConfig

    user = factory.SubFactory(UserFactory)
    storage = factory.SubFactory(StorageFactory)
    auto_apply_threshold = 90
    enable_hourly_snapshots = True
    enable_daily_reconciliation = True
