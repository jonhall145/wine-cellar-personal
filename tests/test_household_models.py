import pytest
from django.utils import timezone

from wine_cellar.apps.household.models import (
    HouseholdMembership,
    HouseholdRole,
    InvitationStatus,
)


@pytest.mark.django_db
def test_household_helpers(
    household_factory, household_membership_factory, user_factory
):
    household = household_factory(name="Sample Household")
    owner = user_factory(username="owner")
    member = user_factory(username="member")

    household_membership_factory(
        household=household, user=owner, role=HouseholdRole.OWNER
    )
    household_membership_factory(
        household=household, user=member, role=HouseholdRole.MEMBER
    )

    assert str(household) == "Sample Household"
    assert household.get_owner() == owner
    assert member in household.get_members()
    assert household.get_member_count() == 2


@pytest.mark.django_db
def test_household_membership_permissions(household_membership_factory):
    membership = household_membership_factory(role=HouseholdRole.MEMBER)

    assert membership.has_role(HouseholdRole.VIEWER) is True
    assert membership.can_edit() is True
    assert membership.can_manage_members() is False
    assert membership.can_delete_household() is False
    assert "Member" in str(membership)


@pytest.mark.django_db
def test_household_invitation_lifecycle(
    household_factory, household_membership_factory, user_factory
):
    household = household_factory()
    inviter = user_factory()
    household_membership_factory(
        household=household, user=inviter, role=HouseholdRole.OWNER
    )
    invitee = user_factory()

    invitation = household.invitations.create(
        email="invitee@example.com",
        invited_by=inviter,
        role=HouseholdRole.MEMBER,
    )

    assert invitation.is_valid() is True
    membership = invitation.accept(invitee)
    assert invitation.status == InvitationStatus.ACCEPTED
    assert membership.household == household
    assert HouseholdMembership.objects.filter(
        household=household, user=invitee
    ).exists()

    invitation.decline()
    assert invitation.status == InvitationStatus.DECLINED

    invitation.status = InvitationStatus.PENDING
    invitation.expires = timezone.now() - timezone.timedelta(days=1)
    invitation.save()
    assert invitation.is_valid() is False
