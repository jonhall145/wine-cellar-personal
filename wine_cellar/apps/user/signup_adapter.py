from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.http import HttpRequest


class ConfigurableSignupAccountAdapter(DefaultAccountAdapter):
    """Account adapter that allows signup to be controlled via settings."""

    def is_open_for_signup(self, request: HttpRequest) -> bool:
        """Check if signups are enabled via ENABLE_SIGNUPS setting."""
        return getattr(settings, "ENABLE_SIGNUPS", False)
