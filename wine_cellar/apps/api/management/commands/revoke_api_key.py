from django.core.management.base import BaseCommand, CommandError

from wine_cellar.apps.api.models import APIKey


class Command(BaseCommand):
    help = "Revoke (deactivate) or delete an API key"

    def add_arguments(self, parser):
        parser.add_argument("key", help="Key prefix or name to revoke")
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Permanently delete instead of deactivating",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Revoke all matching keys (required when multiple keys match)",
        )

    def handle(self, *args, **options):
        identifier = options["key"]
        keys = APIKey.objects.filter(prefix=identifier)
        if not keys.exists():
            keys = APIKey.objects.filter(name=identifier)
        if not keys.exists():
            raise CommandError(f"No API key found matching '{identifier}'")

        count = keys.count()
        if count > 1 and not options["all"]:
            raise CommandError(
                f"Found {count} keys matching '{identifier}'."
                " Use --all to revoke all of them."
            )

        for key in keys:
            if options["delete"]:
                key.delete()
                self.stdout.write(
                    self.style.SUCCESS(f"Deleted key: {key.name} ({key.prefix}...)")
                )
            else:
                key.is_active = False
                key.save(update_fields=["is_active"])
                self.stdout.write(
                    self.style.SUCCESS(f"Revoked key: {key.name} ({key.prefix}...)")
                )
