"""Replay extraction logs to populate grapes that were extracted but never saved."""

from django.core.management.base import BaseCommand

from wine_cellar.apps.wine.models import Grape, VisionExtractionLog, Wine
from wine_cellar.apps.wine.services.grape_normalization import normalize_grape_list


class Command(BaseCommand):
    help = "Populate grape varieties from existing vision extraction logs"

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Actually save changes (default is dry-run)",
        )
        parser.add_argument(
            "--user",
            type=int,
            help="Filter by user ID",
        )

    def handle(self, *args, **options):
        commit = options["commit"]
        mode = "COMMIT" if commit else "DRY RUN"

        self.stdout.write(f"\n=== Replay Extraction Grapes ({mode}) ===\n")

        # Find logs that have grape data in extracted_data
        qs = VisionExtractionLog.objects.all()
        if options["user"]:
            qs = qs.filter(user_id=options["user"])

        wines_updated = 0
        grapes_linked = 0
        grapes_created = 0
        skipped = 0
        logs_linked = 0

        for log in qs:
            data = log.extracted_data or {}
            grape_names = data.get("grapes", [])
            if not grape_names or not isinstance(grape_names, list):
                continue

            name = data.get("name")
            vintage = data.get("vintage")
            if not name:
                continue

            # Normalize and deduplicate grape names
            normalized = normalize_grape_list(grape_names)
            if not normalized:
                continue

            # Match to a wine by name + vintage + user
            wine_qs = Wine.objects.filter(deleted=False, user=log.user)
            wine_qs = wine_qs.filter(name__iexact=name)
            if vintage:
                wine_qs = wine_qs.filter(vintage=vintage)

            wines = list(wine_qs)
            if len(wines) != 1:
                if len(wines) > 1:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  Log {log.pk}: multiple wines match "{name}" '
                            f"({vintage}) - skipping"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  Log {log.pk}: no wine matches "{name}" '
                            f"({vintage}) - skipping"
                        )
                    )
                skipped += 1
                continue

            wine = wines[0]

            # Skip wines that already have grapes (unless log isn't linked)
            if wine.grapes.exists():
                # Still link the log if needed
                if not log.wine_id and commit:
                    log.wine = wine
                    log.save(update_fields=["wine"])
                    logs_linked += 1
                skipped += 1
                continue

            self.stdout.write(f'Log {log.pk} -> Wine {wine.pk} "{wine}"')

            for grape_name in normalized:
                # Check if grape already exists for this user
                existing = Grape.objects.filter(
                    name__iexact=grape_name,
                    user=wine.user,
                ).first()

                if existing:
                    self.stdout.write(f"  -> Link grape: {existing.name} (existing)")
                    if commit:
                        wine.grapes.add(existing)
                else:
                    self.stdout.write(f"  -> Link grape: {grape_name} (new)")
                    if commit:
                        grape = Grape.objects.create(
                            name=grape_name,
                            user=wine.user,
                            household=wine.household,
                        )
                        wine.grapes.add(grape)
                    grapes_created += 1

                grapes_linked += 1

            wines_updated += 1

            # Link log to wine
            if not log.wine_id:
                if commit:
                    log.wine = wine
                    log.save(update_fields=["wine"])
                logs_linked += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n=== Summary ===\n"
                f"Wines updated: {wines_updated}\n"
                f"Grape links created: {grapes_linked}\n"
                f"New grapes: {grapes_created}\n"
                f"Logs linked to wines: {logs_linked}\n"
                f"Skipped: {skipped}\n"
                f"Mode: {mode}"
            )
        )

        if not commit:
            self.stdout.write(self.style.WARNING("\nUse --commit to apply changes"))
