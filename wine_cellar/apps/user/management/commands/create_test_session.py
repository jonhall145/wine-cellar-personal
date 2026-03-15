"""Create an authenticated session for a test user.

Usage:
    python manage.py create_test_session [username]

Creates the user (with household) if it doesn't exist, then prints
the sessionid cookie value for use with httpie, curl, or Playwright.
"""

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.core.management.base import BaseCommand

from wine_cellar.apps.household.models import Household, HouseholdMembership
from wine_cellar.apps.user.models import UserSettings

DEFAULT_USERNAME = "testuser"
DEFAULT_PASSWORD = "testpass123"


class Command(BaseCommand):
    help = "Create an authenticated session for a test user"

    def add_arguments(self, parser):
        parser.add_argument("username", nargs="?", default=DEFAULT_USERNAME)
        parser.add_argument("--password", default=DEFAULT_PASSWORD)

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": f"{username}@test.com"},
        )
        if created:
            user.set_password(password)
            user.save()

        # Ensure household exists
        membership = HouseholdMembership.objects.filter(user=user).first()
        if not membership:
            household = Household.objects.create(name=f"{username}'s household")
            membership = HouseholdMembership.objects.create(
                user=user, household=household, role="OW"
            )

        # Set active household
        settings, _ = UserSettings.objects.get_or_create(user=user)
        if not settings.active_household:
            settings.active_household = membership.household
            settings.save()

        # Create session
        session = SessionStore()
        session["_auth_user_id"] = str(user.pk)
        session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
        session["_auth_user_hash"] = user.get_session_auth_hash()
        session.create()

        self.stdout.write(f"sessionid={session.session_key}")
