"""Management command to analyze vision extraction logs."""

from collections import Counter

from django.core.management.base import BaseCommand
from django.db.models import Avg, Count

from wine_cellar.apps.wine.models import VisionExtractionLog


class Command(BaseCommand):
    help = "Analyze vision extraction logs for quality metrics"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=int,
            help="Filter by user ID",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Number of days to analyze (default: 30)",
        )
        parser.add_argument(
            "--detailed",
            action="store_true",
            help="Show detailed field-level statistics",
        )

    def handle(self, *args, **options):
        from datetime import timedelta

        from django.utils import timezone

        # Build queryset
        qs = VisionExtractionLog.objects.all()

        if options["user"]:
            qs = qs.filter(user_id=options["user"])

        cutoff_date = timezone.now() - timedelta(days=options["days"])
        qs = qs.filter(created__gte=cutoff_date)

        total_count = qs.count()

        if total_count == 0:
            self.stdout.write(self.style.WARNING("No extraction logs found."))
            return

        self.stdout.write(self.style.SUCCESS("\n=== Vision Extraction Analysis ==="))
        self.stdout.write(f"Period: Last {options['days']} days")
        self.stdout.write(f"Total extractions: {total_count}\n")

        # Confidence distribution
        confidence_stats = qs.values("confidence").annotate(count=Count("id"))
        self.stdout.write(self.style.SUCCESS("Confidence Distribution:"))
        for stat in confidence_stats:
            pct = (stat["count"] / total_count) * 100
            self.stdout.write(f"  {stat['confidence']}: {stat['count']} ({pct:.1f}%)")

        # Success rate
        success_count = qs.filter(was_successful=True).count()
        success_rate = (success_count / total_count) * 100 if total_count else 0
        self.stdout.write(
            f"\nSuccess rate: {success_count}/{total_count} ({success_rate:.1f}%)"
        )

        # Processing time stats
        time_stats = qs.filter(processing_time_ms__isnull=False).aggregate(
            avg_time=Avg("processing_time_ms")
        )
        if time_stats["avg_time"]:
            self.stdout.write(
                f"Average processing time: {time_stats['avg_time']:.0f}ms"
            )

        # Image count distribution
        image_stats = (
            qs.values("image_count").annotate(count=Count("id")).order_by("image_count")
        )
        self.stdout.write(self.style.SUCCESS("\nImage Count Distribution:"))
        for stat in image_stats:
            pct = (stat["count"] / total_count) * 100
            self.stdout.write(
                f"  {stat['image_count']} images: {stat['count']} ({pct:.1f}%)"
            )

        # Error analysis
        error_logs = qs.filter(errors__isnull=False).exclude(errors=[])
        error_count = error_logs.count()
        error_rate = (error_count / total_count) * 100 if total_count else 0
        self.stdout.write(
            f"\nExtractions with errors: {error_count} ({error_rate:.1f}%)"
        )

        if options["detailed"]:
            self.stdout.write(self.style.SUCCESS("\n=== Detailed Field Statistics ==="))

            # Field extraction frequency
            field_counter = Counter()
            for log in qs:
                if log.extracted_fields:
                    for field in log.extracted_fields:
                        field_counter[field] += 1

            self.stdout.write("\nField Extraction Frequency:")
            for field, count in field_counter.most_common():
                pct = (count / total_count) * 100
                self.stdout.write(f"  {field}: {count} ({pct:.1f}%)")

            # Model usage
            model_stats = qs.values("model_used").annotate(count=Count("id"))
            self.stdout.write(self.style.SUCCESS("\nModel Usage:"))
            for stat in model_stats:
                pct = (stat["count"] / total_count) * 100
                self.stdout.write(
                    f"  {stat['model_used']}: {stat['count']} ({pct:.1f}%)"
                )

            # Common errors
            if error_count > 0:
                self.stdout.write(self.style.SUCCESS("\nCommon Errors:"))
                error_counter = Counter()
                for log in error_logs:
                    if log.errors:
                        for error in log.errors:
                            # Truncate long errors
                            error_key = error[:100] if len(error) > 100 else error
                            error_counter[error_key] += 1

                for error, count in error_counter.most_common(10):
                    self.stdout.write(f"  [{count}x] {error}")

        self.stdout.write(self.style.SUCCESS("\n=== Analysis Complete ==="))
