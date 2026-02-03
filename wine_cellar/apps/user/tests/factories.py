import factory
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from factory.django import DjangoModelFactory


class UserFactory(DjangoModelFactory):
    class Meta:
        model = get_user_model()
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: "user%d" % n)
    email = factory.Sequence(lambda n: "user%d@wine-cellar.net" % n)
    password = make_password("password")

    @factory.post_generation
    def setup_household(self, create, extracted, **kwargs):
        """Create a default household for the user after creation."""
        if not create:
            return

        from wine_cellar.apps.household.models import (
            Household,
            HouseholdMembership,
            HouseholdRole,
            HouseholdSettings,
        )
        from wine_cellar.apps.storage.models import Storage
        from wine_cellar.apps.user.models import UserSettings

        # Create household
        household = Household.objects.create(name=f"{self.username}'s Cellar")

        # Create owner membership
        HouseholdMembership.objects.create(
            user=self,
            household=household,
            role=HouseholdRole.OWNER,
        )

        # Create household settings
        HouseholdSettings.objects.create(household=household)

        # Update user settings with active household
        user_settings, _ = UserSettings.objects.get_or_create(user=self)
        user_settings.active_household = household
        user_settings.save()

        # Update any storages created by signals to have this household
        Storage.objects.filter(user=self, household__isnull=True).update(
            household=household
        )
