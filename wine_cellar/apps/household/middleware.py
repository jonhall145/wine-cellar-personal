from django.shortcuts import redirect
from django.urls import resolve

from wine_cellar.apps.household.models import HouseholdMembership

# URLs that don't require an active household
EXEMPT_URL_NAMES = {
    # Household management URLs
    "household-list",
    "household-create",
    "household-detail",
    "household-settings",
    "household-rename",
    "household-delete",
    "household-switch",
    "household-leave",
    "household-transfer",
    "member-invite",
    "member-update-role",
    "member-remove",
    "invitation-accept",
    "invitation-decline",
    "invitation-cancel",
    # Authentication URLs
    "account_login",
    "account_logout",
    "account_signup",
    "account_reset_password",
    "account_reset_password_done",
    "account_reset_password_from_key",
    "account_reset_password_from_key_done",
    "account_email_verification_sent",
    "account_confirm_email",
    # Django admin
    "admin:index",
    "admin:login",
    "admin:logout",
    # User settings
    "user-settings",
    "user-update-password",
}

# URL prefixes that don't require an active household
EXEMPT_URL_PREFIXES = {
    "/admin/",
    "/accounts/",
    "/household/",
    "/static/",
    "/media/",
}


class HouseholdMiddleware:
    """
    Middleware to ensure authenticated users have an active household.

    If no active household is set, redirect to household list/setup.
    Also ensures the user is actually a member of their active household.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip for unauthenticated users
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Skip for exempt URLs
        if self._is_exempt_url(request):
            return self.get_response(request)

        # Check if user has valid active household
        user_settings = getattr(request.user, "user_settings", None)
        if not user_settings:
            # UserSettings doesn't exist yet, let the signal create it
            return self.get_response(request)

        active_household = user_settings.active_household

        if active_household:
            # Verify user is still a member of the active household
            if not HouseholdMembership.objects.filter(
                user=request.user,
                household=active_household,
            ).exists():
                # User is no longer a member, clear active household
                user_settings.active_household = None
                user_settings.save()
                active_household = None

        if not active_household:
            # Try to set a default household
            membership = HouseholdMembership.objects.filter(user=request.user).first()
            if membership:
                user_settings.active_household = membership.household
                user_settings.save()
            else:
                # No households, redirect to create one
                return redirect("household-list")

        return self.get_response(request)

    def _is_exempt_url(self, request):
        """Check if the URL is exempt from household requirement."""
        path = request.path

        # Check URL prefixes
        for prefix in EXEMPT_URL_PREFIXES:
            if path.startswith(prefix):
                return True

        # Check URL names
        try:
            resolved = resolve(path)
            if resolved.url_name in EXEMPT_URL_NAMES:
                return True
            # Check namespaced names like admin:index
            if resolved.namespace:
                full_name = f"{resolved.namespace}:{resolved.url_name}"
                if full_name in EXEMPT_URL_NAMES:
                    return True
        except Exception:
            pass

        return False
