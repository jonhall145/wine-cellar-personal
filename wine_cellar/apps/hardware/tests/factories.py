"""Factory classes for hardware app tests."""

import secrets

import factory
from factory.django import DjangoModelFactory

from wine_cellar.apps.hardware.models import (
    HardwareDevice,
    OfflineOperation,
)
from wine_cellar.apps.storage.tests.factories import StorageFactory
from wine_cellar.apps.user.tests.factories import UserFactory


class HardwareDeviceFactory(DjangoModelFactory):
    class Meta:
        model = HardwareDevice

    user = factory.SubFactory(UserFactory)
    name = factory.Faker("word")
    device_id = factory.LazyFunction(lambda: f"pi-{secrets.token_hex(8)}")
    storage = factory.SubFactory(StorageFactory)
    api_token = factory.LazyFunction(lambda: secrets.token_urlsafe(32))
    is_active = True


class OfflineOperationFactory(DjangoModelFactory):
    class Meta:
        model = OfflineOperation

    user = factory.SubFactory(UserFactory)
    device = factory.SubFactory(HardwareDeviceFactory)
    operation_type = "add_wine"
    operation_data = {"wine_id": 1, "rack_id": 1, "row": 1, "col": 1}
    client_timestamp = factory.Faker("date_time_this_year")
