from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone as tz
from django.utils.dateparse import parse_date, parse_datetime

from wine_cellar.apps.api.models import APIKey, APIKeyScope
from wine_cellar.apps.household.models import Household, HouseholdMembership


class Command(BaseCommand):
    help = "Create a new API key for a user/household"

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Human-readable key name")
        parser.add_argument("--user", required=True, help="Username")
        parser.add_argument("--household", required=True, type=int, help="Household ID")
        parser.add_argument(
            "--scope",
            default="read",
            choices=["read", "write", "admin"],
            help="Permission scope (default: read)",
        )
        parser.add_argument(
            "--expires",
            default=None,
            help="Expiry date (ISO format, e.g. 2026-12-31 or 2026-12-31T23:59:59)",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username=options["user"])
        except User.DoesNotExist:
            raise CommandError(f"User '{options['user']}' not found")

        try:
            household = Household.objects.get(pk=options["household"])
        except Household.DoesNotExist:
            raise CommandError(f"Household {options['household']} not found")

        if not HouseholdMembership.objects.filter(
            user=user, household=household
        ).exists():
            raise CommandError(
                f"User '{user.username}' is not a member of household"
                f" '{household.name}'"
            )

        scope_map = {
            "read": APIKeyScope.READ,
            "write": APIKeyScope.WRITE,
            "admin": APIKeyScope.ADMIN,
        }
        scope = scope_map[options["scope"]]

        expires = None
        if options["expires"]:
            expires = parse_datetime(options["expires"])
            if expires is None:
                # Try date-only format (e.g. 2026-12-31) → end of day
                date_val = parse_date(options["expires"])
                if date_val is not None:
                    from datetime import datetime, time

                    expires = datetime.combine(date_val, time.max)
            if expires is not None and tz.is_naive(expires):
                expires = tz.make_aware(expires)
            if expires is None:
                raise CommandError(
                    f"Invalid date format: {options['expires']}."
                    " Use ISO format (e.g. 2026-12-31 or 2026-12-31T23:59:59)"
                )

        raw_key, prefix, hashed_key = APIKey.generate_key()
        APIKey.objects.create(
            name=options["name"],
            prefix=prefix,
            hashed_key=hashed_key,
            user=user,
            household=household,
            scope=scope,
            expires=expires,
        )

        self.stdout.write(self.style.SUCCESS("\nAPI Key created successfully!\n"))
        self.stdout.write(f"  Name:      {options['name']}")
        self.stdout.write(f"  User:      {user.username}")
        self.stdout.write(f"  Household: {household.name} (ID: {household.pk})")
        self.stdout.write(f"  Scope:     {options['scope']}")
        if expires:
            self.stdout.write(f"  Expires:   {expires.isoformat()}")
        else:
            self.stdout.write("  Expires:   never")
        self.stdout.write(f"\n  Key: {raw_key}\n")
        self.stdout.write(
            self.style.WARNING("  Save this key now — it cannot be retrieved again.\n")
        )
