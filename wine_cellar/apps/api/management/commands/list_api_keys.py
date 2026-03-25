from django.core.management.base import BaseCommand

from wine_cellar.apps.api.models import APIKey


class Command(BaseCommand):
    help = "List API keys"

    def add_arguments(self, parser):
        parser.add_argument("--user", default=None, help="Filter by username")

    def handle(self, *args, **options):
        qs = APIKey.objects.select_related("user", "household").order_by("-created")
        if options["user"]:
            qs = qs.filter(user__username=options["user"])

        if not qs.exists():
            self.stdout.write("No API keys found.")
            return

        self.stdout.write(
            f"{'Name':<20} {'Prefix':<10} {'User':<15} {'Household':<20}"
            f" {'Scope':<8} {'Active':<8} {'Last Used':<20} {'Expires':<20}"
        )
        self.stdout.write("-" * 121)

        for key in qs:
            last_used = (
                key.last_used.strftime("%Y-%m-%d %H:%M") if key.last_used else "never"
            )
            expires = key.expires.strftime("%Y-%m-%d %H:%M") if key.expires else "never"
            active = "yes" if key.is_valid else "no"
            self.stdout.write(
                f"{key.name:<20} {key.prefix:<10} {key.user.username:<15}"
                f" {key.household.name:<20} {key.get_scope_display():<8}"
                f" {active:<8} {last_used:<20} {expires:<20}"
            )
