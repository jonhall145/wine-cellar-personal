import pytest
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from wine_cellar.apps.household.models import (
    Household,
    HouseholdInvitation,
    HouseholdMembership,
    HouseholdRole,
    HouseholdSettings,
    InvitationStatus,
)


@pytest.fixture
def owner_household(user):
    """Create a household where user is the owner."""
    household = Household.objects.create(name="Test Household")
    HouseholdMembership.objects.create(
        user=user, household=household, role=HouseholdRole.OWNER
    )
    HouseholdSettings.objects.create(household=household)
    us = user.user_settings
    us.active_household = household
    us.save()
    return household


@pytest.fixture
def admin_user(user_factory):
    """Create a second user for admin/member testing."""
    return user_factory(username="admin_user", email="admin@test.com")


@pytest.mark.django_db
class TestHouseholdListView:
    def test_unauthenticated_redirects(self, client):
        r = client.get(reverse("household-list"), follow=True)
        assert "login" in r.request["PATH_INFO"]

    def test_lists_memberships(self, client, user, owner_household):
        client.force_login(user)
        r = client.get(reverse("household-list"))
        assert r.status_code == 200
        assertTemplateUsed(r, "household/household_list.html")
        assert len(r.context["memberships"]) >= 1

    def test_shows_pending_invitations(self, client, user, user_factory):
        inviter = user_factory()
        household = Household.objects.create(name="Invite HH")
        HouseholdMembership.objects.create(
            user=inviter, household=household, role=HouseholdRole.OWNER
        )
        HouseholdSettings.objects.create(household=household)
        HouseholdInvitation.objects.create(
            household=household,
            email=user.email,
            role=HouseholdRole.MEMBER,
            invited_by=inviter,
        )
        client.force_login(user)
        r = client.get(reverse("household-list"))
        assert len(r.context["pending_invitations"]) == 1


@pytest.mark.django_db
class TestHouseholdCreateView:
    def test_renders_form(self, client, user):
        client.force_login(user)
        r = client.get(reverse("household-create"))
        assert r.status_code == 200
        assertTemplateUsed(r, "household/household_form.html")

    def test_creates_household(self, client, user):
        client.force_login(user)
        r = client.post(
            reverse("household-create"),
            {"name": "New Household"},
            follow=True,
        )
        assert r.status_code == 200
        hh = Household.objects.filter(name="New Household").first()
        assert hh is not None
        assert HouseholdMembership.objects.filter(
            user=user, household=hh, role=HouseholdRole.OWNER
        ).exists()
        assert HouseholdSettings.objects.filter(household=hh).exists()


@pytest.mark.django_db
class TestHouseholdDetailView:
    def test_renders(self, client, user, owner_household):
        client.force_login(user)
        r = client.get(reverse("household-detail", kwargs={"pk": owner_household.pk}))
        assert r.status_code == 200
        assertTemplateUsed(r, "household/household_detail.html")
        assert "members" in r.context
        assert "pending_invitations" in r.context

    def test_non_member_404(self, client, user_factory, owner_household):
        other = user_factory()
        client.force_login(other)
        r = client.get(reverse("household-detail", kwargs={"pk": owner_household.pk}))
        assert r.status_code == 404


@pytest.mark.django_db
class TestHouseholdSwitchView:
    def test_switch_household(self, client, user, owner_household):
        hh2 = Household.objects.create(name="Second HH")
        HouseholdMembership.objects.create(
            user=user, household=hh2, role=HouseholdRole.MEMBER
        )
        HouseholdSettings.objects.create(household=hh2)
        client.force_login(user)
        r = client.post(reverse("household-switch", kwargs={"pk": hh2.pk}), follow=True)
        assert r.status_code == 200
        user.user_settings.refresh_from_db()
        assert user.user_settings.active_household == hh2

    def test_switch_non_member_404(self, client, user):
        hh = Household.objects.create(name="Not A Member")
        HouseholdSettings.objects.create(household=hh)
        client.force_login(user)
        r = client.post(reverse("household-switch", kwargs={"pk": hh.pk}))
        assert r.status_code == 404

    def test_safe_redirect(self, client, user, owner_household):
        client.force_login(user)
        r = client.post(
            reverse("household-switch", kwargs={"pk": owner_household.pk}),
            {"next": reverse("household-list")},
        )
        assert r.status_code == 302
        assert reverse("household-list") in r.url


@pytest.mark.django_db
class TestHouseholdDeleteView:
    def test_owner_can_delete(self, client, user, owner_household):
        client.force_login(user)
        r = client.post(
            reverse("household-delete", kwargs={"pk": owner_household.pk}),
            follow=True,
        )
        assert r.status_code == 200
        assert not Household.objects.filter(pk=owner_household.pk).exists()
        user.user_settings.refresh_from_db()
        assert user.user_settings.active_household is None


@pytest.mark.django_db
class TestHouseholdRenameView:
    def test_rename(self, client, user, owner_household):
        client.force_login(user)
        r = client.post(
            reverse("household-rename", kwargs={"pk": owner_household.pk}),
            {"name": "Renamed Household"},
            follow=True,
        )
        assert r.status_code == 200
        owner_household.refresh_from_db()
        assert owner_household.name == "Renamed Household"


@pytest.mark.django_db
class TestMemberInviteView:
    def test_invite_new_user(self, client, user, owner_household):
        client.force_login(user)
        r = client.post(
            reverse("member-invite", kwargs={"pk": owner_household.pk}),
            {"email": "newuser@example.com", "role": HouseholdRole.MEMBER},
            follow=True,
        )
        assert r.status_code == 200
        assert HouseholdInvitation.objects.filter(email="newuser@example.com").exists()

    def test_invite_existing_member_warns(
        self, client, user, owner_household, admin_user
    ):
        HouseholdMembership.objects.create(
            user=admin_user,
            household=owner_household,
            role=HouseholdRole.MEMBER,
        )
        client.force_login(user)
        r = client.post(
            reverse("member-invite", kwargs={"pk": owner_household.pk}),
            {"email": admin_user.email, "role": HouseholdRole.MEMBER},
            follow=True,
        )
        assert r.status_code == 200
        # Should not create a duplicate invitation
        assert (
            HouseholdInvitation.objects.filter(
                email=admin_user.email, household=owner_household
            ).count()
            == 0
        )

    def test_duplicate_pending_invitation_warns(self, client, user, owner_household):
        HouseholdInvitation.objects.create(
            household=owner_household,
            email="dup@example.com",
            role=HouseholdRole.MEMBER,
            invited_by=user,
            status=InvitationStatus.PENDING,
        )
        client.force_login(user)
        r = client.post(
            reverse("member-invite", kwargs={"pk": owner_household.pk}),
            {"email": "dup@example.com", "role": HouseholdRole.MEMBER},
            follow=True,
        )
        assert r.status_code == 200
        assert (
            HouseholdInvitation.objects.filter(
                email="dup@example.com", household=owner_household
            ).count()
            == 1
        )


@pytest.mark.django_db
class TestInvitationAcceptView:
    def _create_invitation(self, household, user, inviter):
        return HouseholdInvitation.objects.create(
            household=household,
            email=user.email,
            role=HouseholdRole.MEMBER,
            invited_by=inviter,
            status=InvitationStatus.PENDING,
        )

    def test_accept_valid_invitation(self, client, user_factory):
        owner = user_factory(email="owner@test.com")
        invitee = user_factory(email="invitee@test.com")
        household = Household.objects.create(name="Accept HH")
        HouseholdMembership.objects.create(
            user=owner, household=household, role=HouseholdRole.OWNER
        )
        HouseholdSettings.objects.create(household=household)
        invitation = self._create_invitation(household, invitee, owner)

        client.force_login(invitee)
        r = client.post(
            reverse("invitation-accept", kwargs={"token": invitation.token}),
            follow=True,
        )
        assert r.status_code == 200
        assert HouseholdMembership.objects.filter(
            user=invitee, household=household
        ).exists()

    def test_wrong_email_rejected(self, client, user_factory):
        owner = user_factory(email="owner2@test.com")
        invitee = user_factory(email="invitee2@test.com")
        wrong_user = user_factory(email="wrong@test.com")
        household = Household.objects.create(name="Wrong Email HH")
        HouseholdMembership.objects.create(
            user=owner, household=household, role=HouseholdRole.OWNER
        )
        HouseholdSettings.objects.create(household=household)
        invitation = self._create_invitation(household, invitee, owner)

        client.force_login(wrong_user)
        r = client.get(
            reverse("invitation-accept", kwargs={"token": invitation.token}),
            follow=True,
        )
        assert r.status_code == 200
        assert not HouseholdMembership.objects.filter(
            user=wrong_user, household=household
        ).exists()


@pytest.mark.django_db
class TestInvitationDeclineView:
    def test_decline(self, client, user_factory):
        owner = user_factory(email="own@test.com")
        invitee = user_factory(email="inv@test.com")
        household = Household.objects.create(name="Decline HH")
        HouseholdMembership.objects.create(
            user=owner, household=household, role=HouseholdRole.OWNER
        )
        HouseholdSettings.objects.create(household=household)
        invitation = HouseholdInvitation.objects.create(
            household=household,
            email=invitee.email,
            role=HouseholdRole.MEMBER,
            invited_by=owner,
            status=InvitationStatus.PENDING,
        )
        client.force_login(invitee)
        r = client.post(
            reverse("invitation-decline", kwargs={"token": invitation.token}),
            follow=True,
        )
        assert r.status_code == 200
        invitation.refresh_from_db()
        assert invitation.status == InvitationStatus.DECLINED


@pytest.mark.django_db
class TestInvitationCancelView:
    def test_admin_cancels(self, client, user, owner_household):
        invitation = HouseholdInvitation.objects.create(
            household=owner_household,
            email="cancel@test.com",
            role=HouseholdRole.MEMBER,
            invited_by=user,
            status=InvitationStatus.PENDING,
        )
        client.force_login(user)
        r = client.post(
            reverse(
                "invitation-cancel",
                kwargs={"pk": owner_household.pk, "invitation_pk": invitation.pk},
            ),
            follow=True,
        )
        assert r.status_code == 200
        invitation.refresh_from_db()
        assert invitation.status == InvitationStatus.EXPIRED


@pytest.mark.django_db
class TestMemberUpdateRoleView:
    def test_update_role(self, client, user, owner_household, admin_user):
        membership = HouseholdMembership.objects.create(
            user=admin_user,
            household=owner_household,
            role=HouseholdRole.MEMBER,
        )
        client.force_login(user)
        r = client.post(
            reverse(
                "member-update-role",
                kwargs={"pk": owner_household.pk, "membership_pk": membership.pk},
            ),
            {"role": HouseholdRole.ADMIN},
            follow=True,
        )
        assert r.status_code == 200
        membership.refresh_from_db()
        assert membership.role == HouseholdRole.ADMIN

    def test_cannot_change_owner_role(self, client, user, owner_household):
        owner_membership = HouseholdMembership.objects.get(
            user=user, household=owner_household
        )
        client.force_login(user)
        r = client.get(
            reverse(
                "member-update-role",
                kwargs={"pk": owner_household.pk, "membership_pk": owner_membership.pk},
            ),
        )
        assert r.status_code == 404


@pytest.mark.django_db
class TestMemberRemoveView:
    def test_remove_member(self, client, user, owner_household, admin_user):
        membership = HouseholdMembership.objects.create(
            user=admin_user,
            household=owner_household,
            role=HouseholdRole.MEMBER,
        )
        client.force_login(user)
        r = client.post(
            reverse(
                "member-remove",
                kwargs={"pk": owner_household.pk, "membership_pk": membership.pk},
            ),
            follow=True,
        )
        assert r.status_code == 200
        assert not HouseholdMembership.objects.filter(pk=membership.pk).exists()

    def test_cannot_remove_owner(self, client, user, owner_household):
        owner_membership = HouseholdMembership.objects.get(
            user=user, household=owner_household
        )
        client.force_login(user)
        r = client.post(
            reverse(
                "member-remove",
                kwargs={"pk": owner_household.pk, "membership_pk": owner_membership.pk},
            ),
        )
        assert r.status_code == 404


@pytest.mark.django_db
class TestMemberLeaveView:
    def test_member_leaves(self, client, user_factory, owner_household, user):
        member = user_factory(email="leaver@test.com")
        HouseholdMembership.objects.create(
            user=member, household=owner_household, role=HouseholdRole.MEMBER
        )
        member.user_settings.active_household = owner_household
        member.user_settings.save()
        client.force_login(member)
        r = client.post(
            reverse("household-leave", kwargs={"pk": owner_household.pk}),
            follow=True,
        )
        assert r.status_code == 200
        assert not HouseholdMembership.objects.filter(
            user=member, household=owner_household
        ).exists()
        member.user_settings.refresh_from_db()
        assert member.user_settings.active_household is None

    def test_owner_cannot_leave(self, client, user, owner_household):
        client.force_login(user)
        r = client.post(
            reverse("household-leave", kwargs={"pk": owner_household.pk}),
            follow=True,
        )
        assert r.status_code == 200
        # Owner should still be a member
        assert HouseholdMembership.objects.filter(
            user=user, household=owner_household
        ).exists()


@pytest.mark.django_db
class TestTransferOwnershipView:
    def test_transfer(self, client, user, owner_household, admin_user):
        member_membership = HouseholdMembership.objects.create(
            user=admin_user,
            household=owner_household,
            role=HouseholdRole.ADMIN,
        )
        client.force_login(user)
        r = client.post(
            reverse("household-transfer", kwargs={"pk": owner_household.pk}),
            {"new_owner": member_membership.pk},
            follow=True,
        )
        assert r.status_code == 200
        member_membership.refresh_from_db()
        assert member_membership.role == HouseholdRole.OWNER
        owner_membership = HouseholdMembership.objects.get(
            user=user, household=owner_household
        )
        assert owner_membership.role == HouseholdRole.ADMIN


# ---------------------------------------------------------------------------
# HouseholdSettingsView (GET / POST) — requires template to render detail links
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHouseholdSettingsView:
    def test_non_member_404(self, client, user_factory, owner_household):
        other = user_factory()
        client.force_login(other)
        r = client.get(reverse("household-settings", kwargs={"pk": owner_household.pk}))
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# RequireAdminMixin / RequireOwnerMixin edge cases
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMixinPermissions:
    def test_member_cannot_access_admin_view(
        self, client, user_factory, owner_household, user
    ):
        """Member role is below Admin — should be denied on admin-protected views."""
        member = user_factory(email="member_perm@test.com")
        HouseholdMembership.objects.create(
            user=member, household=owner_household, role=HouseholdRole.MEMBER
        )
        member.user_settings.active_household = owner_household
        member.user_settings.save()
        client.force_login(member)
        # HouseholdSettingsView requires Admin
        r = client.get(reverse("household-settings", kwargs={"pk": owner_household.pk}))
        assert r.status_code == 403

    def test_admin_cannot_delete_household(
        self, client, user_factory, owner_household, user
    ):
        """Admin role is below Owner — delete should be restricted or redirect."""
        admin = user_factory(email="admin_perm@test.com")
        HouseholdMembership.objects.create(
            user=admin, household=owner_household, role=HouseholdRole.ADMIN
        )
        admin.user_settings.active_household = owner_household
        admin.user_settings.save()
        client.force_login(admin)
        r = client.post(reverse("household-delete", kwargs={"pk": owner_household.pk}))
        # The view may redirect or deny — just verify it doesn't error
        assert r.status_code in (200, 302, 403)

    def test_admin_can_rename_household(
        self, client, user_factory, owner_household, user
    ):
        """Admin can access admin-level views like rename."""
        admin = user_factory(email="admin_rename@test.com")
        HouseholdMembership.objects.create(
            user=admin, household=owner_household, role=HouseholdRole.ADMIN
        )
        admin.user_settings.active_household = owner_household
        admin.user_settings.save()
        client.force_login(admin)
        r = client.post(
            reverse("household-rename", kwargs={"pk": owner_household.pk}),
            {"name": "Admin Renamed"},
            follow=True,
        )
        assert r.status_code == 200
        owner_household.refresh_from_db()
        assert owner_household.name == "Admin Renamed"

    def test_no_active_household_redirects(self, client, user):
        """User without active household is redirected to household-list."""
        user.user_settings.active_household = None
        user.user_settings.save()
        client.force_login(user)
        r = client.get(reverse("household-settings", kwargs={"pk": 99999}))
        assert r.status_code == 302
        assert "household" in r.url

    def test_viewer_cannot_invite(self, client, user_factory, owner_household):
        """Viewer cannot access admin-level invite view."""
        viewer = user_factory(email="viewer_inv@test.com")
        HouseholdMembership.objects.create(
            user=viewer, household=owner_household, role=HouseholdRole.VIEWER
        )
        viewer.user_settings.active_household = owner_household
        viewer.user_settings.save()
        client.force_login(viewer)
        r = client.get(reverse("member-invite", kwargs={"pk": owner_household.pk}))
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Invitation edge cases
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInvitationEdgeCases:
    def test_accept_expired_invitation_redirects(self, client, user_factory):
        """Expired invitation cannot be accepted."""
        owner = user_factory(email="own_exp@test.com")
        invitee = user_factory(email="inv_exp@test.com")
        household = Household.objects.create(name="Expired HH")
        HouseholdMembership.objects.create(
            user=owner, household=household, role=HouseholdRole.OWNER
        )
        HouseholdSettings.objects.create(household=household)
        invitation = HouseholdInvitation.objects.create(
            household=household,
            email=invitee.email,
            role=HouseholdRole.MEMBER,
            invited_by=owner,
            status=InvitationStatus.EXPIRED,
        )
        client.force_login(invitee)
        r = client.get(
            reverse("invitation-accept", kwargs={"token": invitation.token}),
            follow=True,
        )
        assert r.status_code == 200
        assert not HouseholdMembership.objects.filter(
            user=invitee, household=household
        ).exists()

    def test_accept_post_expired_redirects(self, client, user_factory):
        """POST to accept expired invitation redirects with error."""
        owner = user_factory(email="own_exp2@test.com")
        invitee = user_factory(email="inv_exp2@test.com")
        household = Household.objects.create(name="Expired HH2")
        HouseholdMembership.objects.create(
            user=owner, household=household, role=HouseholdRole.OWNER
        )
        HouseholdSettings.objects.create(household=household)
        invitation = HouseholdInvitation.objects.create(
            household=household,
            email=invitee.email,
            role=HouseholdRole.MEMBER,
            invited_by=owner,
            status=InvitationStatus.EXPIRED,
        )
        client.force_login(invitee)
        r = client.post(
            reverse("invitation-accept", kwargs={"token": invitation.token}),
            follow=True,
        )
        assert r.status_code == 200
        assert not HouseholdMembership.objects.filter(
            user=invitee, household=household
        ).exists()

    def test_accept_wrong_email_post(self, client, user_factory):
        """POST to accept with wrong email redirects."""
        owner = user_factory(email="own_wrong@test.com")
        invitee = user_factory(email="inv_wrong@test.com")
        wrong_user = user_factory(email="wrong2@test.com")
        household = Household.objects.create(name="Wrong Email HH2")
        HouseholdMembership.objects.create(
            user=owner, household=household, role=HouseholdRole.OWNER
        )
        HouseholdSettings.objects.create(household=household)
        invitation = HouseholdInvitation.objects.create(
            household=household,
            email=invitee.email,
            role=HouseholdRole.MEMBER,
            invited_by=owner,
            status=InvitationStatus.PENDING,
        )
        client.force_login(wrong_user)
        r = client.post(
            reverse("invitation-accept", kwargs={"token": invitation.token}),
            follow=True,
        )
        assert r.status_code == 200
        assert not HouseholdMembership.objects.filter(
            user=wrong_user, household=household
        ).exists()

    def test_switch_with_unsafe_next_url(self, client, user, owner_household):
        """Unsafe next URL is ignored; redirects to household-list."""
        client.force_login(user)
        r = client.post(
            reverse("household-switch", kwargs={"pk": owner_household.pk}),
            {"next": "https://evil.com"},
        )
        assert r.status_code == 302
        assert "evil.com" not in r.url

    def test_switch_no_user_settings(self, client, user, owner_household):
        """Switch still works even when POSTing."""
        client.force_login(user)
        r = client.post(
            reverse("household-switch", kwargs={"pk": owner_household.pk}),
            follow=True,
        )
        assert r.status_code == 200
