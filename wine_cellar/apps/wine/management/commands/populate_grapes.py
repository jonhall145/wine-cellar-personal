"""Batch populate grape varieties for wines using Claude AI."""

import time

from django.conf import settings
from django.core.management.base import BaseCommand

from wine_cellar.apps.wine.models import Grape, Wine
from wine_cellar.apps.wine.services.ai_grapes import WineAIGrapeService


class Command(BaseCommand):
    help = "Populate grape varieties for wines with empty grapes using Claude AI"

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
        parser.add_argument(
            "--limit",
            type=int,
            help="Maximum number of wines to process",
        )
        parser.add_argument(
            "--skip-images",
            action="store_true",
            help="Skip sending label images (metadata-only, cheaper)",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.0,
            help="Delay in seconds between API calls (default: 1.0)",
        )

    def handle(self, *args, **options):
        api_key = getattr(settings, "ANTHROPIC_API_KEY", None)
        if not api_key:
            self.stderr.write(
                self.style.ERROR("ANTHROPIC_API_KEY not configured in settings")
            )
            return

        commit = options["commit"]
        mode = "COMMIT" if commit else "DRY RUN"
        delay = options["delay"]

        self.stdout.write(f"\n=== Populate Grapes via AI ({mode}) ===\n")

        # Query wines with no grapes
        qs = Wine.objects.filter(deleted=False, grapes__isnull=True).distinct()
        if options["user"]:
            qs = qs.filter(user_id=options["user"])
        qs = qs.select_related("size").prefetch_related("wineimage_set")
        if options["limit"]:
            qs = qs[: options["limit"]]

        wines = list(qs)
        total = len(wines)

        if total == 0:
            self.stdout.write("No wines found with empty grapes.")
            return

        self.stdout.write(f"Found {total} wines to process\n")

        wines_updated = 0
        grapes_linked = 0
        grapes_created = 0
        skipped = 0
        errors = 0

        for idx, wine in enumerate(wines, 1):
            try:
                grape_names, confidence = WineAIGrapeService.identify_grapes(
                    wine,
                    include_images=not options["skip_images"],
                )

                wine_type = wine.get_wine_type_display() if wine.wine_type else "?"
                self.stdout.write(
                    f'[{idx}/{total}] "{wine}" ({wine_type}, {wine.country})'
                )

                if not grape_names:
                    self.stdout.write("  -> No grapes identified")
                    skipped += 1
                else:
                    for grape_name in grape_names:
                        existing = Grape.objects.filter(
                            name__iexact=grape_name,
                            user=wine.user,
                        ).first()

                        if existing:
                            self.stdout.write(
                                f"  -> {existing.name} (existing, {confidence})"
                            )
                            if commit:
                                wine.grapes.add(existing)
                        else:
                            self.stdout.write(f"  -> {grape_name} (new, {confidence})")
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

                # Rate limiting
                if idx < total:
                    time.sleep(delay)

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'[{idx}/{total}] Error for "{wine}": {e}')
                )
                errors += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n=== Summary ===\n"
                f"Wines processed: {total}\n"
                f"Wines updated: {wines_updated}\n"
                f"Grape links: {grapes_linked}\n"
                f"New grapes: {grapes_created}\n"
                f"Skipped (no grapes identified): {skipped}\n"
                f"Errors: {errors}\n"
                f"Mode: {mode}"
            )
        )

        if not commit:
            self.stdout.write(self.style.WARNING("\nUse --commit to apply changes"))
