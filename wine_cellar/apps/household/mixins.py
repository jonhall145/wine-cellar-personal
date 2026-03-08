from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http.response import HttpResponseRedirectBase
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _

from wine_cellar.apps.household.models import (
    ROLE_HIERARCHY,
    HouseholdMembership,
    HouseholdRole,
)


def require_member(view_func):
    """Decorator for function-based views that require Member role."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from wine_cellar.apps.user.views import get_active_household

        household = get_active_household(request.user)
        if not household:
            return redirect("household-list")
        try:
            membership = HouseholdMembership.objects.get(
                user=request.user, household=household
            )
        except HouseholdMembership.DoesNotExist:
            raise PermissionDenied(
                _("You need Member role or higher to perform this action.")
            )
        if ROLE_HIERARCHY.get(membership.role, 0) < ROLE_HIERARCHY.get(
            HouseholdRole.MEMBER, 0
        ):
            raise PermissionDenied(
                _("You need Member role or higher to perform this action.")
            )
        return view_func(request, *args, **kwargs)

    return wrapper


class HouseholdContextMixin:
    """
    Mixin that provides household context for views.

    Provides methods to get the current household and membership,
    and automatically filters querysets by household.
    """

    def get_household(self):
        """Get the active household for the current user."""
        if not hasattr(self, "_household_cache"):
            user = self.request.user
            if hasattr(user, "user_settings") and user.user_settings.active_household:
                self._household_cache = user.user_settings.active_household
            else:
                self._household_cache = None
        return self._household_cache

    def get_membership(self):
        """Get the current user's membership in the active household."""
        if not hasattr(self, "_membership_cache"):
            household = self.get_household()
            if household:
                try:
                    self._membership_cache = HouseholdMembership.objects.get(
                        user=self.request.user,
                        household=household,
                    )
                except HouseholdMembership.DoesNotExist:
                    self._membership_cache = None
            else:
                self._membership_cache = None
        return self._membership_cache

    def has_role(self, min_role):
        """Check if the current user has at least the specified role."""
        membership = self.get_membership()
        if not membership:
            return False
        return ROLE_HIERARCHY.get(membership.role, 0) >= ROLE_HIERARCHY.get(min_role, 0)

    def can_edit(self):
        """Check if the current user can create/edit/delete content."""
        return self.has_role(HouseholdRole.MEMBER)

    def can_manage_members(self):
        """Check if the current user can manage household members."""
        return self.has_role(HouseholdRole.ADMIN)

    def is_owner(self):
        """Check if the current user is the household owner."""
        membership = self.get_membership()
        return membership and membership.role == HouseholdRole.OWNER

    def get_queryset(self):
        """Filter the queryset by the current household."""
        qs = super().get_queryset()
        household = self.get_household()
        if household:
            return qs.filter(household=household)
        return qs.none()

    def get_context_data(self, **kwargs):
        """Add household context to the template."""
        context = super().get_context_data(**kwargs)
        context["household"] = self.get_household()
        context["membership"] = self.get_membership()
        context["can_edit"] = self.can_edit()
        context["can_manage_members"] = self.can_manage_members()
        context["is_owner"] = self.is_owner()
        return context


class RequireHouseholdMixin(HouseholdContextMixin):
    """
    Mixin that requires the user to have an active household.

    Redirects to household setup if no active household is set.
    """

    def dispatch(self, request, *args, **kwargs):
        if not self.get_household():
            messages.warning(
                request,
                _("Please select or create a household to continue."),
            )
            return redirect("household-list")
        return super().dispatch(request, *args, **kwargs)


class RequireMemberMixin(RequireHouseholdMixin):
    """
    Mixin that requires the user to have at least Member role.

    Use this for views that modify content (create, update, delete).
    """

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if isinstance(response, HttpResponseRedirectBase):
            return response

        if not self.can_edit():
            messages.error(
                request,
                _("You don't have permission to modify content in this household."),
            )
            raise PermissionDenied(
                _("You need Member role or higher to perform this action.")
            )
        return response


class RequireAdminMixin(RequireHouseholdMixin):
    """
    Mixin that requires the user to have at least Admin role.

    Use this for views that manage household members.
    """

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if isinstance(response, HttpResponseRedirectBase):
            return response

        if not self.can_manage_members():
            messages.error(
                request,
                _("You don't have permission to manage members in this household."),
            )
            raise PermissionDenied(
                _("You need Admin role or higher to perform this action.")
            )
        return response


class RequireOwnerMixin(RequireHouseholdMixin):
    """
    Mixin that requires the user to be the household owner.

    Use this for views that delete the household or transfer ownership.
    """

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if isinstance(response, HttpResponseRedirectBase):
            return response

        if not self.is_owner():
            messages.error(
                request,
                _("Only the household owner can perform this action."),
            )
            raise PermissionDenied(
                _("You need to be the household owner to perform this action.")
            )
        return response
