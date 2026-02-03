import random

import factory
from factory.django import DjangoModelFactory

from wine_cellar.apps.storage.models import Storage, StorageItem
from wine_cellar.apps.user.tests.factories import UserFactory
from wine_cellar.apps.wine.tests.factories import WineFactory


class StorageFactory(DjangoModelFactory):
    class Meta:
        model = Storage

    name = factory.Faker("name")
    location = factory.Faker("address")
    rows = random.randint(1, 10)
    columns = random.randint(1, 10)
    user = factory.SubFactory(UserFactory)

    @factory.lazy_attribute
    def household(self):
        """Set household from user's active household."""
        if hasattr(self.user, "user_settings") and self.user.user_settings:
            return self.user.user_settings.active_household
        return None


class StorageItemFactory(DjangoModelFactory):
    class Meta:
        model = StorageItem

    storage = factory.SubFactory(StorageFactory)
    wine = factory.SubFactory(WineFactory)

    @factory.lazy_attribute
    def user(self):
        """Set user from storage."""
        return self.storage.user

    @factory.lazy_attribute
    def household(self):
        """Set household from storage."""
        return self.storage.household
