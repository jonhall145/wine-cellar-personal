import factory
from factory.django import DjangoModelFactory

from wine_cellar.apps.household.models import (
    Household,
    HouseholdMembership,
    HouseholdRole,
    HouseholdSettings,
)


class HouseholdFactory(DjangoModelFactory):
    class Meta:
        model = Household

    name = factory.Sequence(lambda n: "Household %d" % n)


class HouseholdMembershipFactory(DjangoModelFactory):
    class Meta:
        model = HouseholdMembership

    user = factory.SubFactory("wine_cellar.apps.user.tests.factories.UserFactory")
    household = factory.SubFactory(HouseholdFactory)
    role = HouseholdRole.MEMBER


class HouseholdSettingsFactory(DjangoModelFactory):
    class Meta:
        model = HouseholdSettings

    household = factory.SubFactory(HouseholdFactory)
