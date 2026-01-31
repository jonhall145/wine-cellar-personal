from celery import shared_task
from django.contrib.auth import get_user_model
from django.db.models import Max
from django.utils import timezone

from wine_cellar.apps.wine.emails import send_drink_by_reminder, send_sale_alert
from wine_cellar.apps.wine.models import PriceHistory, SaleAlert, Wine


@shared_task(name="drink_by_reminder")
def drink_by_reminder():
    """Send reminders for wines in their final drinking year."""
    User = get_user_model()
    users = (
        User.objects.exclude(email__isnull=True)
        .exclude(email__exact="")
        .exclude(user_settings__notifications=False)
    )
    current_year = timezone.now().year
    for user in users:
        # Find wines where drink_to matches current year (not "now" which is 0)
        wines = Wine.objects.filter(
            user=user,
            drink_to=current_year,
            storageitem__isnull=False,
            storageitem__deleted=False,
        ).distinct()
        if wines.count() > 0:
            send_drink_by_reminder(user, wines)


@shared_task(name="check_sale_alerts")
def check_sale_alerts():
    """Check for price drops and send sale alerts."""
    now = timezone.now()

    # Get all active alerts for users with notifications enabled
    alerts = (
        SaleAlert.objects.filter(
            is_active=True,
            user__email__isnull=False,
        )
        .exclude(user__email__exact="")
        .exclude(user__user_settings__notifications=False)
        .select_related("wine", "source", "user")
    )

    for alert in alerts:
        triggered_deals = []

        # Build base query for price history
        price_query = PriceHistory.objects.filter(user=alert.user)

        if alert.wine:
            price_query = price_query.filter(wine=alert.wine)
        if alert.source:
            price_query = price_query.filter(source=alert.source)

        # Get wines with recent price entries
        wines_with_prices = (
            price_query.values("wine", "source")
            .annotate(latest_date=Max("recorded_at"))
            .filter(
                latest_date__gte=alert.last_notified
                or timezone.datetime.min.replace(tzinfo=timezone.utc)
            )
        )

        for entry in wines_with_prices:
            # Get the latest price
            latest = (
                PriceHistory.objects.filter(
                    user=alert.user,
                    wine_id=entry["wine"],
                    source_id=entry["source"],
                )
                .order_by("-recorded_at")
                .first()
            )

            if not latest:
                continue

            # Get the previous price before this one
            previous = (
                PriceHistory.objects.filter(
                    user=alert.user,
                    wine_id=entry["wine"],
                    source_id=entry["source"],
                    recorded_at__lt=latest.recorded_at,
                )
                .order_by("-recorded_at")
                .first()
            )

            should_alert = False

            # Check threshold price
            if alert.threshold_price and latest.price <= alert.threshold_price:
                should_alert = True

            # Check percentage drop
            if previous and alert.threshold_percent:
                drop_pct = (previous.price - latest.price) / previous.price * 100
                if drop_pct >= alert.threshold_percent:
                    should_alert = True

            if should_alert:
                triggered_deals.append(
                    {
                        "wine": latest.wine,
                        "source": latest.source,
                        "current_price": latest.price,
                        "previous_price": previous.price if previous else None,
                    }
                )

        # Send notification if any deals found
        if triggered_deals:
            send_sale_alert(alert.user, triggered_deals)
            alert.last_notified = now
            alert.save(update_fields=["last_notified"])
