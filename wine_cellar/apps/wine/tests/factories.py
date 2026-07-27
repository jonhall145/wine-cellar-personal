import random

import factory
from factory import post_generation
from factory.django import DjangoModelFactory, ImageField

from wine_cellar.apps.user.tests.factories import UserFactory
from wine_cellar.apps.wine.models import (
    Attribute,
    FoodPairing,
    Grape,
    Size,
    SizeChoices,
    Source,
    Vineyard,
    Wine,
    WineBarcode,
    WineImage,
    WineType,
)


def get_household_from_user(obj):
    """Helper to get household from user's active household."""
    if hasattr(obj, "user") and obj.user:
        if hasattr(obj.user, "user_settings") and obj.user.user_settings:
            return obj.user.user_settings.active_household
    return None


class GrapeFactory(DjangoModelFactory):
    class Meta:
        model = Grape

    name = factory.Sequence(lambda n: f"Grape {n}")
    # user and household are nullable - only set if explicitly passed


class SizeFactory(DjangoModelFactory):
    class Meta:
        model = Size

    name = random.choice([choice[0] for choice in SizeChoices.choices])
    # user and household are nullable - only set if explicitly passed


class VineyardFactory(DjangoModelFactory):
    class Meta:
        model = Vineyard

    name = factory.Faker("company")
    # user and household are nullable - only set if explicitly passed


class FoodPairingFactory(DjangoModelFactory):
    class Meta:
        model = FoodPairing

    name = factory.Faker("name")
    # user and household are nullable - only set if explicitly passed


class AttributeFactory(DjangoModelFactory):
    class Meta:
        model = Attribute

    name = factory.Faker("name")
    # user and household are nullable - only set if explicitly passed


class SourceFactory(DjangoModelFactory):
    class Meta:
        model = Source

    name = factory.Faker("name")
    # user and household are nullable - only set if explicitly passed


class WineFactory(DjangoModelFactory):
    class Meta:
        model = Wine
        skip_postgeneration_save = True

    user = factory.SubFactory(UserFactory)
    name = factory.Faker("name")
    wine_type = random.choice(WineType.choices)[0]
    vintage = random.randint(1900, 2024)
    abv = 12.0
    country = "DE"

    @factory.lazy_attribute
    def household(self):
        return get_household_from_user(self)

    @post_generation
    def grapes(obj, create, extracted, **kwargs):
        if not create:
            return
        if not extracted:
            grape = GrapeFactory(user=obj.user, household=obj.household)
            obj.grapes.add(grape)
        else:
            obj.save()
            for grape in extracted:
                obj.grapes.add(grape)


class WineBarcodeFactory(DjangoModelFactory):
    class Meta:
        model = WineBarcode

    wine = factory.SubFactory(WineFactory)
    barcode = factory.Faker("ean13")
    user = factory.LazyAttribute(lambda o: o.wine.user)
    household = factory.LazyAttribute(lambda o: o.wine.household)


class WineImageFactory(DjangoModelFactory):
    class Meta:
        model = WineImage

    image = ImageField()
    wine = factory.SubFactory(WineFactory)
    user = factory.SubFactory(UserFactory)
