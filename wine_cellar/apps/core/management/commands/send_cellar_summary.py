from django.core.management.base import BaseCommand

from wine_cellar.apps.core.emails import send_cellar_summary_emails


class Command(BaseCommand):
    help = "Send weekly or monthly cellar summary emails."

    def add_arguments(self, parser):
        parser.add_argument(
            "--period",
            choices=("weekly", "monthly"),
            default="weekly",
            help="Choose whether to send a weekly or monthly digest.",
        )

    def handle(self, *args, **options):
        period = options["period"]
        sent = send_cellar_summary_emails(period=period)
        self.stdout.write(f"Sent {sent} {period} summary email(s)")
