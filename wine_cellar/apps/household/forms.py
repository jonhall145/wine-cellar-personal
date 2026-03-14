from django import forms

from wine_cellar.apps.household.models import (
    Household,
    HouseholdInvitation,
    HouseholdMembership,
    HouseholdRole,
    HouseholdSettings,
)


class HouseholdForm(forms.ModelForm):
    """Form for creating and editing households."""

    class Meta:
        model = Household
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
        }


class HouseholdSettingsForm(forms.ModelForm):
    """Form for editing household settings."""

    class Meta:
        model = HouseholdSettings
        fields = ["currency", "notifications"]
        widgets = {
            "currency": forms.Select(attrs={"class": "form-select"}),
            "notifications": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class HouseholdInvitationForm(forms.ModelForm):
    """Form for inviting users to a household."""

    # Limit role choices - can't invite someone as owner
    role = forms.ChoiceField(
        choices=[
            (HouseholdRole.VIEWER, "Viewer - Read-only access"),
            (HouseholdRole.MEMBER, "Member - Can add and edit wines"),
            (HouseholdRole.ADMIN, "Admin - Can also manage members"),
        ],
        initial=HouseholdRole.MEMBER,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = HouseholdInvitation
        fields = ["email", "role"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }


class MembershipRoleForm(forms.ModelForm):
    """Form for editing a member's role."""

    # Limit role choices - can't change someone to owner
    role = forms.ChoiceField(
        choices=[
            (HouseholdRole.VIEWER, "Viewer"),
            (HouseholdRole.MEMBER, "Member"),
            (HouseholdRole.ADMIN, "Admin"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = HouseholdMembership
        fields = ["role"]


class TransferOwnershipForm(forms.Form):
    """Form for transferring household ownership."""

    new_owner = forms.ModelChoiceField(
        queryset=HouseholdMembership.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="New Owner",
    )

    def __init__(self, household, current_user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show other members as potential new owners
        self.fields["new_owner"].queryset = HouseholdMembership.objects.filter(
            household=household
        ).exclude(user=current_user)
        self.fields["new_owner"].label_from_instance = (
            lambda obj: f"{obj.user.username} ({obj.get_role_display()})"
        )
