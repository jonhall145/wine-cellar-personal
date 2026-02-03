import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class HouseholdRole(models.TextChoices):
    VIEWER = "VI", _("Viewer")  # Read-only
    MEMBER = "ME", _("Member")  # CRUD data
    ADMIN = "AD", _("Admin")  # + manage members
    OWNER = "OW", _("Owner")  # + delete household


# Role hierarchy for permission checks
ROLE_HIERARCHY = {
    HouseholdRole.VIEWER: 0,
    HouseholdRole.MEMBER: 1,
    HouseholdRole.ADMIN: 2,
    HouseholdRole.OWNER: 3,
}


class InvitationStatus(models.TextChoices):
    PENDING = "PE", _("Pending")
    ACCEPTED = "AC", _("Accepted")
    DECLINED = "DE", _("Declined")
    EXPIRED = "EX", _("Expired")


class Household(models.Model):
    name = models.CharField(max_length=100, verbose_name=_("Household Name"))
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("Created"))
    modified = models.DateTimeField(auto_now=True, verbose_name=_("Modified"))

    class Meta:
        verbose_name = _("Household")
        verbose_name_plural = _("Households")

    def __str__(self):
        return self.name

    def get_owner(self):
        """Return the owner of the household."""
        membership = self.memberships.filter(role=HouseholdRole.OWNER).first()
        return membership.user if membership else None

    def get_members(self):
        """Return all members of the household."""
        return (
            get_user_model()
            .objects.filter(household_memberships__household=self)
            .distinct()
        )

    def get_member_count(self):
        """Return the number of members in the household."""
        return self.memberships.count()


class HouseholdMembership(models.Model):
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="household_memberships",
        verbose_name=_("User"),
    )
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("Household"),
    )
    role = models.CharField(
        max_length=2,
        choices=HouseholdRole.choices,
        default=HouseholdRole.MEMBER,
        verbose_name=_("Role"),
    )
    joined = models.DateTimeField(auto_now_add=True, verbose_name=_("Joined"))
    invited_by = models.ForeignKey(
        get_user_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invitations_sent",
        verbose_name=_("Invited By"),
    )

    class Meta:
        verbose_name = _("Household Membership")
        verbose_name_plural = _("Household Memberships")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "household"],
                name="unique_household_membership",
            )
        ]

    def __str__(self):
        role_display = self.get_role_display()
        return f"{self.user.username} - {self.household.name} ({role_display})"

    def has_role(self, min_role):
        """Check if the membership has at least the given role level."""
        return ROLE_HIERARCHY.get(self.role, 0) >= ROLE_HIERARCHY.get(min_role, 0)

    def can_edit(self):
        """Check if this member can create/edit/delete content."""
        return self.has_role(HouseholdRole.MEMBER)

    def can_manage_members(self):
        """Check if this member can invite/remove members."""
        return self.has_role(HouseholdRole.ADMIN)

    def can_delete_household(self):
        """Check if this member can delete the household."""
        return self.role == HouseholdRole.OWNER


def generate_invitation_token():
    """Generate a secure random token for invitations."""
    return secrets.token_urlsafe(48)


def get_invitation_expiry():
    """Get default expiry date for invitations (7 days from now)."""
    return timezone.now() + timezone.timedelta(days=7)


class HouseholdInvitation(models.Model):
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="invitations",
        verbose_name=_("Household"),
    )
    email = models.EmailField(verbose_name=_("Email"))
    role = models.CharField(
        max_length=2,
        choices=HouseholdRole.choices,
        default=HouseholdRole.MEMBER,
        verbose_name=_("Role"),
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        default=generate_invitation_token,
        verbose_name=_("Token"),
    )
    invited_by = models.ForeignKey(
        get_user_model(),
        null=True,
        on_delete=models.SET_NULL,
        related_name="household_invitations_created",
        verbose_name=_("Invited By"),
    )
    status = models.CharField(
        max_length=2,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
        verbose_name=_("Status"),
    )
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("Created"))
    expires = models.DateTimeField(
        default=get_invitation_expiry,
        verbose_name=_("Expires"),
    )

    class Meta:
        verbose_name = _("Household Invitation")
        verbose_name_plural = _("Household Invitations")
        indexes = [
            models.Index(fields=["token"], name="invitation_token_idx"),
            models.Index(
                fields=["email", "status"], name="invitation_email_status_idx"
            ),
        ]

    def __str__(self):
        return f"Invitation to {self.household.name} for {self.email}"

    def is_valid(self):
        """Check if the invitation is still valid."""
        return self.status == InvitationStatus.PENDING and self.expires > timezone.now()

    def accept(self, user):
        """Accept the invitation and create membership."""
        if not self.is_valid():
            return None

        membership, created = HouseholdMembership.objects.get_or_create(
            user=user,
            household=self.household,
            defaults={
                "role": self.role,
                "invited_by": self.invited_by,
            },
        )

        self.status = InvitationStatus.ACCEPTED
        self.save()

        return membership

    def decline(self):
        """Decline the invitation."""
        self.status = InvitationStatus.DECLINED
        self.save()


class HouseholdSettings(models.Model):
    household = models.OneToOneField(
        Household,
        on_delete=models.CASCADE,
        related_name="settings",
        verbose_name=_("Household"),
    )
    language = models.CharField(
        max_length=7,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE,
        verbose_name=_("Language"),
    )
    currency = models.CharField(
        max_length=3,
        choices=settings.CURRENCIES,
        default="EUR",
        verbose_name=_("Currency"),
    )
    notifications = models.BooleanField(
        default=True,
        verbose_name=_("Notifications"),
    )

    class Meta:
        verbose_name = _("Household Settings")
        verbose_name_plural = _("Household Settings")

    def __str__(self):
        return f"Settings for {self.household.name}"
