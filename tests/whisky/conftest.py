import os

# Whisky tests require CELLAR_APP_TYPE=whisky to be set BEFORE Django loads.
# Run these tests with:  CELLAR_APP_TYPE=whisky pytest tests/whisky/
# Guard all imports so this conftest is safe to load in wine mode (pytest always
# loads conftest.py files from subdirectories regardless of collect_ignore).
if os.environ.get("CELLAR_APP_TYPE") == "whisky":
    import factory
    from factory.django import DjangoModelFactory
    from pytest_factoryboy import register

    from wine_cellar.apps.storage.tests.factories import StorageFactory
    from wine_cellar.apps.user.tests.factories import UserFactory
    from wine_cellar.apps.whisky.models import (
        Bottler,
        CaskHistory,
        CaskTypeChoice,
        Distillery,
        FillLevel,
        PreviousContents,
        Whisky,
        WhiskyRegion,
        WhiskyStorageItem,
        WhiskyType,
    )

    # -------------------------------------------------------------------
    # Factories
    # -------------------------------------------------------------------

    class WhiskyRegionFactory(DjangoModelFactory):
        class Meta:
            model = WhiskyRegion

        name = factory.Sequence(lambda n: "Region %d" % n)
        slug = factory.Sequence(lambda n: "region-%d" % n)
        country = "GB"
        order = factory.Sequence(lambda n: n)

    class DistilleryFactory(DjangoModelFactory):
        class Meta:
            model = Distillery

        name = factory.Sequence(lambda n: "Distillery %d" % n)
        region = factory.SubFactory(WhiskyRegionFactory)
        country = "GB"
        status = "AC"

    class BottlerFactory(DjangoModelFactory):
        class Meta:
            model = Bottler

        name = factory.Sequence(lambda n: "Bottler %d" % n)
        country = "GB"

    class WhiskyFactory(DjangoModelFactory):
        class Meta:
            model = Whisky
            skip_postgeneration_save = True

        user = factory.SubFactory(UserFactory)
        name = factory.Sequence(lambda n: "Whisky %d" % n)
        whisky_type = WhiskyType.SINGLE_MALT
        abv = 46.0
        country = "GB"

        @factory.lazy_attribute
        def household(self):
            if hasattr(self.user, "user_settings") and self.user.user_settings:
                return self.user.user_settings.active_household
            return None

    class CaskHistoryFactory(DjangoModelFactory):
        class Meta:
            model = CaskHistory

        whisky = factory.SubFactory(WhiskyFactory)
        order = factory.Sequence(lambda n: n + 1)
        cask_type = CaskTypeChoice.HOGSHEAD
        previous_contents = PreviousContents.BOURBON

    class WhiskyStorageItemFactory(DjangoModelFactory):
        class Meta:
            model = WhiskyStorageItem

        storage = factory.SubFactory(StorageFactory)
        whisky = factory.SubFactory(WhiskyFactory)
        fill_level = FillLevel.FULL

        @factory.lazy_attribute
        def user(self):
            return self.storage.user

        @factory.lazy_attribute
        def household(self):
            return self.storage.household

    # -------------------------------------------------------------------
    # Register factories with pytest-factoryboy
    # -------------------------------------------------------------------

    register(WhiskyRegionFactory)
    register(DistilleryFactory)
    register(BottlerFactory)
    register(WhiskyFactory)
    register(CaskHistoryFactory)
    register(WhiskyStorageItemFactory)
