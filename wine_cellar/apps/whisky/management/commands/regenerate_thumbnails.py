"""
Management command to regenerate all whisky image thumbnails.

Usage (requires virtual environment):
    source venv/bin/activate
    CELLAR_APP_TYPE=whisky python manage.py regenerate_thumbnails

Options:
    --dry-run    Preview what would be processed without making changes
"""

from django.core.management.base import BaseCommand

from wine_cellar.apps.whisky.models import WhiskyImage
from wine_cellar.apps.wine.utils import make_thumbnail


class Command(BaseCommand):
    """Regenerate all whisky image thumbnails."""

    help = "Regenerate all whisky image thumbnails"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        images = WhiskyImage.objects.filter(image__isnull=False).exclude(image="")
        total = images.count()

        self.stdout.write(f"Found {total} images to process")

        success_count = 0
        error_count = 0

        for i, whisky_image in enumerate(images, 1):
            self.stdout.write(f"[{i}/{total}] Processing: {whisky_image.image.name}")

            if not dry_run:
                try:
                    thumb_name = make_thumbnail(whisky_image)
                    whisky_image.thumbnail.name = thumb_name
                    whisky_image.save(update_fields=["thumbnail"])
                    self.stdout.write(self.style.SUCCESS(f"  -> {thumb_name}"))
                    success_count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  -> Error: {e}"))
                    error_count += 1
            else:
                self.stdout.write("  -> [DRY RUN] Would regenerate")
                success_count += 1

        self.stdout.write("")
        if dry_run:
            msg = f"Dry run complete. {total} images would be processed."
            self.stdout.write(self.style.SUCCESS(msg))
        else:
            msg = f"Done! {success_count} succeeded, {error_count} failed."
            self.stdout.write(self.style.SUCCESS(msg))
