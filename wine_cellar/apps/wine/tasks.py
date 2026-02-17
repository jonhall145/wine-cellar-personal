import logging
import re
from decimal import Decimal, InvalidOperation

import requests
from bs4 import BeautifulSoup
from celery import shared_task
from django.contrib.auth import get_user_model
from django.db.models import Max
from django.utils import timezone

from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.wine.emails import send_drink_by_reminder, send_sale_alert
from wine_cellar.apps.wine.models import PriceHistory, SaleAlert, Wine

logger = logging.getLogger(__name__)


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
        # Get the user's active household
        household = get_active_household(user)
        if not household:
            continue
        # Find wines where drink_to matches current year (not "now" which is 0)
        wines = Wine.objects.filter(
            household=household,
            drink_to=current_year,
            storageitem__isnull=False,
            storageitem__deleted=False,
        ).distinct()
        if wines.count() > 0:
            send_drink_by_reminder(user, wines)


@shared_task(name="check_sale_alerts")
def check_sale_alerts():
    """Check for price drops and send sale alerts."""
    from collections import defaultdict

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

        # Get the user's active household
        household = get_active_household(alert.user)
        if not household:
            continue

        # Build base query for price history
        price_query = PriceHistory.objects.filter(household=household)

        if alert.wine:
            price_query = price_query.filter(wine=alert.wine)
        if alert.source:
            price_query = price_query.filter(source=alert.source)

        # Get wines with recent price entries
        last_notified = alert.last_notified or timezone.datetime.min.replace(
            tzinfo=timezone.UTC
        )
        wines_with_prices = (
            price_query.values("wine", "source")
            .annotate(latest_date=Max("recorded_at"))
            .filter(latest_date__gte=last_notified)
        )

        if not wines_with_prices:
            continue

        # Batch fetch all relevant prices at once to avoid N+1 queries
        wine_source_pairs = [(e["wine"], e["source"]) for e in wines_with_prices]
        all_prices = (
            PriceHistory.objects.filter(household=household)
            .filter(
                wine_id__in=[p[0] for p in wine_source_pairs],
                source_id__in=[p[1] for p in wine_source_pairs],
            )
            .select_related("wine", "source")
            .order_by("wine_id", "source_id", "-recorded_at")
        )

        # Group prices by (wine_id, source_id)
        prices_by_key = defaultdict(list)
        for price in all_prices:
            key = (price.wine_id, price.source_id)
            prices_by_key[key].append(price)

        # Process each wine/source combination
        for wine_id, source_id in wine_source_pairs:
            prices = prices_by_key.get((wine_id, source_id), [])
            if not prices:
                continue

            latest = prices[0]  # Already ordered by -recorded_at
            previous = prices[1] if len(prices) > 1 else None

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


@shared_task(name="fetch_wine_prices")
def fetch_wine_prices():
    """Fetch prices from wine URLs and record in PriceHistory."""
    # Get wines with price_url configured
    wines = (
        Wine.objects.filter(
            price_url__isnull=False,
        )
        .exclude(price_url="")
        .select_related("user")
        .prefetch_related("source")
    )

    fetched_count = 0
    for wine in wines:
        # Get first source with a price_selector
        source = (
            wine.source.filter(price_selector__isnull=False)
            .exclude(price_selector="")
            .first()
        )
        if not source:
            continue

        try:
            response = requests.get(
                wine.price_url,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0 (compatible; WineCellar/1.0)"},
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            price_element = soup.select_one(source.price_selector)

            if price_element:
                price_text = price_element.get_text(strip=True)
                # Extract numeric value (handles $19.99, €19,99, etc.)
                price_match = re.search(r"[\d.,]+", price_text)
                if price_match:
                    price_str = price_match.group()
                    # Handle European format (1.234,56 -> 1234.56)
                    if "," in price_str and "." in price_str:
                        # Determine which is the decimal separator
                        if price_str.rfind(",") > price_str.rfind("."):
                            # European: 1.234,56
                            price_str = price_str.replace(".", "").replace(",", ".")
                        else:
                            # US: 1,234.56
                            price_str = price_str.replace(",", "")
                    elif "," in price_str:
                        # Could be European decimal (19,99) or US thousands (1,000)
                        # Assume decimal if only one comma and 2 digits after
                        parts = price_str.split(",")
                        if len(parts) == 2 and len(parts[1]) == 2:
                            price_str = price_str.replace(",", ".")
                        else:
                            price_str = price_str.replace(",", "")

                    price = Decimal(price_str)

                    PriceHistory.objects.create(
                        wine=wine,
                        source=source,
                        price=price,
                        user=wine.user,
                        household=wine.household,
                    )
                    fetched_count += 1
        except requests.RequestException as e:
            logger.warning(f"Price fetch failed for {wine.name}: {e}")
        except InvalidOperation as e:
            logger.warning(f"Price parse failed for {wine.name}: {e}")

    return f"Fetched {fetched_count} prices"
