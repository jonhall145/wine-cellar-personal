"""Batch populate grape varieties for wines using Claude AI."""

import re
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from wine_cellar.apps.wine.models import Grape, Wine, WineImage
from wine_cellar.apps.wine.services.grape_normalization import (
    normalize_grape_list,
)


def build_grape_prompt(wine):
    """Build a Claude prompt to identify grape varieties for a wine."""
    import pycountry

    country_name = "Unknown"
    if wine.country:
        country = pycountry.countries.get(alpha_2=wine.country)
        if country:
            country_name = country.name

    wine_type_display = wine.get_wine_type_display() if wine.wine_type else "Unknown"

    return f"""You are a wine expert. Given the following wine information, \
identify the most likely grape varieties used to make this wine.

Wine Name: {wine.name}
Wine Type: {wine_type_display}
Country: {country_name}
Region: {wine.subregion or "Unknown"}
Comment: {wine.comment or "None"}

Rules:
- Return ONLY grape variety names you are confident about
- Use full canonical names in title case (e.g., "Cabernet Sauvignon")
- For well-known regional wines, infer grapes from the appellation/region
- If the wine name itself is a grape variety, include it
- If you cannot determine the grapes with reasonable confidence, return "not found"
- Do not guess wildly - only return grapes you would bet on

Return in this exact format:
GRAPES: grape1, grape2, grape3
CONFIDENCE: high/medium/low"""


def parse_grape_response(response_text):
    """Parse a Claude response for grape names and confidence."""
    grapes = []
    confidence = "low"

    grape_match = re.search(r"GRAPES:\s*(.+?)(?:\n|$)", response_text, re.IGNORECASE)
    if grape_match:
        raw = grape_match.group(1).strip()
        if raw.lower() != "not found":
            grapes = normalize_grape_list(raw.split(","))

    conf_match = re.search(r"CONFIDENCE:\s*(.+?)(?:\n|$)", response_text, re.IGNORECASE)
    if conf_match:
        conf = conf_match.group(1).strip().lower()
        if conf in ("high", "medium", "low"):
            confidence = conf

    return grapes, confidence


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

        try:
            import anthropic
        except ImportError:
            self.stderr.write(self.style.ERROR("anthropic package not installed"))
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

        client = anthropic.Anthropic(api_key=api_key)

        wines_updated = 0
        grapes_linked = 0
        grapes_created = 0
        skipped = 0
        errors = 0

        for idx, wine in enumerate(wines, 1):
            try:
                # Build prompt
                prompt_text = build_grape_prompt(wine)

                # Build content
                content = []

                # Optionally include label images
                if not options["skip_images"]:
                    images = WineImage.objects.filter(wine=wine)
                    for img in images[:2]:  # Max 2 images
                        try:
                            import base64

                            from wine_cellar.apps.wine.services.vision_extraction import (  # noqa: E501
                                resize_image_for_api,
                            )

                            with img.image.open("rb") as f:
                                image_data = f.read()
                            b64 = base64.b64encode(image_data).decode("utf-8")
                            resized = resize_image_for_api(b64)
                            content.append(
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/jpeg",
                                        "data": resized,
                                    },
                                }
                            )
                        except Exception as e:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  Could not load image for wine {wine.pk}: {e}"
                                )
                            )

                content.append({"type": "text", "text": prompt_text})

                # Call Claude API
                response = client.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=256,
                    messages=[{"role": "user", "content": content}],
                )

                response_text = response.content[0].text
                grape_names, confidence = parse_grape_response(response_text)

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
