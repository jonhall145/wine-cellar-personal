from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from wine_cellar.apps.household.forms import (
    HouseholdForm,
    HouseholdInvitationForm,
    HouseholdSettingsForm,
    MembershipRoleForm,
    TransferOwnershipForm,
)
from wine_cellar.apps.household.mixins import (
    RequireAdminMixin,
    RequireOwnerMixin,
)
from wine_cellar.apps.household.models import (
    Household,
    HouseholdInvitation,
    HouseholdMembership,
    HouseholdRole,
    HouseholdSettings,
    InvitationStatus,
)


class HouseholdListView(LoginRequiredMixin, ListView):
    """List all households the user belongs to."""

    model = HouseholdMembership
    template_name = "household/household_list.html"
    context_object_name = "memberships"

    def get_queryset(self):
        return (
            HouseholdMembership.objects.filter(user=self.request.user)
            .select_related("household", "household__settings")
            .order_by("household__name")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get pending invitations for the user
        context["pending_invitations"] = HouseholdInvitation.objects.filter(
            email=self.request.user.email,
            status=InvitationStatus.PENDING,
        ).select_related("household", "invited_by")
        return context


class HouseholdCreateView(LoginRequiredMixin, CreateView):
    """Create a new household."""

    model = Household
    form_class = HouseholdForm
    template_name = "household/household_form.html"
    success_url = reverse_lazy("household-list")

    def form_valid(self, form):
        with transaction.atomic():
            # Save the household
            response = super().form_valid(form)

            # Create owner membership
            HouseholdMembership.objects.create(
                user=self.request.user,
                household=self.object,
                role=HouseholdRole.OWNER,
            )

            # Create default settings
            HouseholdSettings.objects.create(household=self.object)

            # Set as active household if user doesn't have one
            user_settings = getattr(self.request.user, "user_settings", None)
            if user_settings and not user_settings.active_household:
                user_settings.active_household = self.object
                user_settings.save()

            messages.success(
                self.request,
                _("Household '%(name)s' created successfully.")
                % {"name": self.object.name},
            )
        return response


class HouseholdDetailView(LoginRequiredMixin, DetailView):
    """View household details."""

    model = Household
    template_name = "household/household_detail.html"
    context_object_name = "household"

    def get_queryset(self):
        # Only show households the user belongs to
        return Household.objects.filter(memberships__user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["membership"] = get_object_or_404(
            HouseholdMembership,
            user=self.request.user,
            household=self.object,
        )
        context["members"] = self.object.memberships.select_related(
            "user", "invited_by"
        ).order_by("-role", "user__username")
        context["pending_invitations"] = self.object.invitations.filter(
            status=InvitationStatus.PENDING
        ).select_related("invited_by")
        return context


class HouseholdSettingsView(RequireAdminMixin, UpdateView):
    """Edit household settings."""

    model = HouseholdSettings
    form_class = HouseholdSettingsForm
    template_name = "household/household_settings.html"

    def get_object(self, queryset=None):
        household = get_object_or_404(
            Household,
            pk=self.kwargs["pk"],
            memberships__user=self.request.user,
        )
        # Set the household for RequireAdminMixin
        self._household_cache = household
        return household.settings

    def get_success_url(self):
        return reverse("household-detail", kwargs={"pk": self.kwargs["pk"]})

    def form_valid(self, form):
        messages.success(self.request, _("Household settings updated."))
        return super().form_valid(form)


class HouseholdRenameView(RequireAdminMixin, UpdateView):
    """Rename a household."""

    model = Household
    form_class = HouseholdForm
    template_name = "household/household_rename.html"

    def get_queryset(self):
        return Household.objects.filter(memberships__user=self.request.user)

    def get_object(self, queryset=None):
        household = super().get_object(queryset)
        self._household_cache = household
        return household

    def get_success_url(self):
        return reverse("household-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(
            self.request,
            _("Household renamed to '%(name)s'.") % {"name": form.cleaned_data["name"]},
        )
        return super().form_valid(form)


class HouseholdDeleteView(RequireOwnerMixin, DeleteView):
    """Delete a household."""

    model = Household
    template_name = "household/household_confirm_delete.html"
    success_url = reverse_lazy("household-list")

    def get_queryset(self):
        return Household.objects.filter(memberships__user=self.request.user)

    def get_object(self, queryset=None):
        household = super().get_object(queryset)
        self._household_cache = household
        return household

    def form_valid(self, form):
        household_name = self.object.name
        # Clear active household for all affected users
        from wine_cellar.apps.user.models import UserSettings

        UserSettings.objects.filter(active_household=self.object).update(
            active_household=None
        )
        messages.success(
            self.request,
            _("Household '%(name)s' has been deleted.") % {"name": household_name},
        )
        return super().form_valid(form)


class HouseholdSwitchView(LoginRequiredMixin, View):
    """Switch the active household."""

    def post(self, request, pk):
        # Verify user is a member of this household
        membership = get_object_or_404(
            HouseholdMembership,
            user=request.user,
            household_id=pk,
        )

        # Update active household
        user_settings = getattr(request.user, "user_settings", None)
        if user_settings:
            user_settings.active_household = membership.household
            user_settings.save()
            messages.success(
                request,
                _("Switched to household '%(name)s'.")
                % {"name": membership.household.name},
            )
        else:
            messages.error(request, _("Unable to switch household."))

        # Redirect to referring page or household list as a safe default
        safe_default_url = reverse("household-list")
        next_url = (request.POST.get("next") or "").strip()
        if url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            redirect_to = next_url
        else:
            redirect_to = safe_default_url
        return redirect(redirect_to)


class MemberInviteView(RequireAdminMixin, CreateView):
    """Invite a user to the household."""

    model = HouseholdInvitation
    form_class = HouseholdInvitationForm
    template_name = "household/member_invite.html"

    def get_household(self):
        if not hasattr(self, "_household_cache"):
            self._household_cache = get_object_or_404(
                Household,
                pk=self.kwargs["pk"],
                memberships__user=self.request.user,
            )
        return self._household_cache

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["household"] = self.get_household()
        return context

    def form_valid(self, form):
        form.instance.household = self.get_household()
        form.instance.invited_by = self.request.user

        # Check if user is already a member
        email = form.cleaned_data["email"]
        User = get_user_model()
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            if HouseholdMembership.objects.filter(
                user=existing_user, household=form.instance.household
            ).exists():
                messages.warning(
                    self.request,
                    _("This user is already a member of the household."),
                )
                return redirect("household-detail", pk=self.kwargs["pk"])

        # Check for existing pending invitation
        existing_invitation = HouseholdInvitation.objects.filter(
            household=form.instance.household,
            email=email,
            status=InvitationStatus.PENDING,
        ).first()
        if existing_invitation:
            messages.warning(
                self.request,
                _("An invitation has already been sent to this email."),
            )
            return redirect("household-detail", pk=self.kwargs["pk"])

        response = super().form_valid(form)
        messages.success(
            self.request,
            _("Invitation sent to %(email)s.") % {"email": email},
        )
        # TODO: Send invitation email
        return response

    def get_success_url(self):
        return reverse("household-detail", kwargs={"pk": self.kwargs["pk"]})


class InvitationAcceptView(LoginRequiredMixin, TemplateView):
    """Accept a household invitation."""

    template_name = "household/invitation_accept.html"

    def get_invitation(self):
        return get_object_or_404(
            HouseholdInvitation,
            token=self.kwargs["token"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["invitation"] = self.get_invitation()
        return context

    def get(self, request, *args, **kwargs):
        invitation = self.get_invitation()

        # Check if invitation is valid
        if not invitation.is_valid():
            messages.error(
                request, _("This invitation has expired or is no longer valid.")
            )
            return redirect("household-list")

        # Check if email matches
        if invitation.email.lower() != request.user.email.lower():
            messages.error(
                request,
                _("This invitation was sent to a different email address."),
            )
            return redirect("household-list")

        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        invitation = self.get_invitation()

        if not invitation.is_valid():
            messages.error(
                request, _("This invitation has expired or is no longer valid.")
            )
            return redirect("household-list")

        if invitation.email.lower() != request.user.email.lower():
            messages.error(
                request,
                _("This invitation was sent to a different email address."),
            )
            return redirect("household-list")

        # Accept the invitation
        membership = invitation.accept(request.user)
        if membership:
            messages.success(
                request,
                _("You have joined '%(name)s'.") % {"name": invitation.household.name},
            )
            # Set as active household if user doesn't have one
            user_settings = getattr(request.user, "user_settings", None)
            if user_settings and not user_settings.active_household:
                user_settings.active_household = invitation.household
                user_settings.save()
        else:
            messages.error(request, _("Unable to accept invitation."))

        return redirect("household-list")


class InvitationDeclineView(LoginRequiredMixin, View):
    """Decline a household invitation."""

    def post(self, request, token):
        invitation = get_object_or_404(
            HouseholdInvitation,
            token=token,
            email=request.user.email,
            status=InvitationStatus.PENDING,
        )
        invitation.decline()
        messages.info(
            request,
            _("Invitation to '%(name)s' declined.")
            % {"name": invitation.household.name},
        )
        return redirect("household-list")


class InvitationCancelView(RequireAdminMixin, View):
    """Cancel a pending invitation (by admin)."""

    def get_household(self):
        if not hasattr(self, "_household_cache"):
            self._household_cache = get_object_or_404(
                Household,
                pk=self.kwargs["pk"],
                memberships__user=self.request.user,
            )
        return self._household_cache

    def post(self, request, pk, invitation_pk):
        invitation = get_object_or_404(
            HouseholdInvitation,
            pk=invitation_pk,
            household_id=pk,
            status=InvitationStatus.PENDING,
        )
        invitation.status = InvitationStatus.EXPIRED
        invitation.save()
        messages.info(request, _("Invitation cancelled."))
        return redirect("household-detail", pk=pk)


class MemberUpdateRoleView(RequireAdminMixin, UpdateView):
    """Update a member's role."""

    model = HouseholdMembership
    form_class = MembershipRoleForm
    template_name = "household/member_role_form.html"
    pk_url_kwarg = "membership_pk"

    def get_household(self):
        if not hasattr(self, "_household_cache"):
            self._household_cache = get_object_or_404(
                Household,
                pk=self.kwargs["pk"],
                memberships__user=self.request.user,
            )
        return self._household_cache

    def get_queryset(self):
        return HouseholdMembership.objects.filter(household_id=self.kwargs["pk"])

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Can't change owner's role
        if obj.role == HouseholdRole.OWNER:
            raise Http404(_("Cannot change owner's role."))
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["household"] = self.get_household()
        context["member"] = self.object
        return context

    def get_success_url(self):
        return reverse("household-detail", kwargs={"pk": self.kwargs["pk"]})

    def form_valid(self, form):
        messages.success(
            self.request,
            _("Role updated for %(user)s.") % {"user": self.object.user.username},
        )
        return super().form_valid(form)


class MemberRemoveView(RequireAdminMixin, DeleteView):
    """Remove a member from the household."""

    model = HouseholdMembership
    template_name = "household/member_confirm_remove.html"
    pk_url_kwarg = "membership_pk"

    def get_household(self):
        if not hasattr(self, "_household_cache"):
            self._household_cache = get_object_or_404(
                Household,
                pk=self.kwargs["pk"],
                memberships__user=self.request.user,
            )
        return self._household_cache

    def get_queryset(self):
        return HouseholdMembership.objects.filter(household_id=self.kwargs["pk"])

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Can't remove owner
        if obj.role == HouseholdRole.OWNER:
            raise Http404(_("Cannot remove the owner."))
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["household"] = self.get_household()
        context["member"] = self.object
        return context

    def get_success_url(self):
        return reverse("household-detail", kwargs={"pk": self.kwargs["pk"]})

    def form_valid(self, form):
        username = self.object.user.username
        # Clear this household as active if it was
        from wine_cellar.apps.user.models import UserSettings

        UserSettings.objects.filter(
            user=self.object.user,
            active_household=self.object.household,
        ).update(active_household=None)

        messages.success(
            self.request,
            _("%(user)s has been removed from the household.") % {"user": username},
        )
        return super().form_valid(form)


class MemberLeaveView(LoginRequiredMixin, View):
    """Leave a household (for non-owners)."""

    def post(self, request, pk):
        membership = get_object_or_404(
            HouseholdMembership,
            user=request.user,
            household_id=pk,
        )

        if membership.role == HouseholdRole.OWNER:
            messages.error(
                request,
                _(
                    "Owners cannot leave the household. "
                    "Transfer ownership first or delete the household."
                ),
            )
            return redirect("household-detail", pk=pk)

        household_name = membership.household.name

        # Clear this household as active if it was
        user_settings = getattr(request.user, "user_settings", None)
        if user_settings and user_settings.active_household_id == pk:
            user_settings.active_household = None
            user_settings.save()

        membership.delete()
        messages.success(
            request,
            _("You have left '%(name)s'.") % {"name": household_name},
        )
        return redirect("household-list")


class TransferOwnershipView(RequireOwnerMixin, FormView):
    """Transfer household ownership to another member."""

    template_name = "household/transfer_ownership.html"
    form_class = TransferOwnershipForm

    def get_household(self):
        if not hasattr(self, "_household_cache"):
            self._household_cache = get_object_or_404(
                Household,
                pk=self.kwargs["pk"],
                memberships__user=self.request.user,
            )
        return self._household_cache

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["household"] = self.get_household()
        kwargs["current_user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["household"] = self.get_household()
        return context

    def form_valid(self, form):
        household = self.get_household()
        new_owner_membership = form.cleaned_data["new_owner"]

        with transaction.atomic():
            # Change new owner's role
            new_owner_membership.role = HouseholdRole.OWNER
            new_owner_membership.save()

            # Demote current owner to admin
            current_membership = HouseholdMembership.objects.get(
                user=self.request.user,
                household=household,
            )
            current_membership.role = HouseholdRole.ADMIN
            current_membership.save()

        messages.success(
            self.request,
            _("Ownership transferred to %(user)s.")
            % {"user": new_owner_membership.user.username},
        )
        return redirect("household-detail", pk=household.pk)
