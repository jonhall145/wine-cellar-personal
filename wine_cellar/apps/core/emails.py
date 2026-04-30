import logging
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import Coalesce
from django.template.loader import render_to_string

from wine_cellar.apps.user.views import get_active_household, get_user_settings

logger = logging.getLogger(__name__)

SUMMARY_PERIODS = {"weekly": 7, "monthly": 30}


def _absolute_url(path: str) -> str:
    return f"{settings.SITE_URL.rstrip('/')}{path}"


def _format_currency(amount: Decimal, currency_symbol: str) -> str:
    return f"{currency_symbol}{amount.quantize(Decimal('0.01'))}"


def _base_context(
    *,
    user,
    household,
    app_name: str,
    period: str,
    total_items_label: str,
    total_items: int,
    total_value: str,
    bottles_in_stock: int,
    low_stock_count: int,
    total_consumed: int,
    avg_rating: float | None,
    wishlist_count: int,
):
    return {
        "user": user,
        "household": household,
        "app_name": app_name,
        "period": period,
        "period_label": period.capitalize(),
        "total_items_label": total_items_label,
        "total_items": total_items,
        "total_value": total_value,
        "bottles_in_stock": bottles_in_stock,
        "low_stock_count": low_stock_count,
        "total_consumed": total_consumed,
        "avg_rating": f"{avg_rating:.1f}/3" if avg_rating is not None else "—",
        "wishlist_count": wishlist_count,
        "summary_url": _absolute_url("/"),
        "alerts_url": _absolute_url("/alerts/"),
    }


def build_cellar_summary_context(user, period: str = "weekly"):
    if period not in SUMMARY_PERIODS:
        raise ValueError(f"Unsupported summary period: {period}")

    household = get_active_household(user)
    if not household:
        return None

    app_type = getattr(settings, "CELLAR_APP_TYPE", "wine")
    if app_type == "whisky":
        return _build_whisky_summary_context(user, household, period)
    return _build_wine_summary_context(user, household, period)


def send_cellar_summary_email(user, period: str = "weekly") -> bool:
    if not user.email:
        return False

    context = build_cellar_summary_context(user, period=period)
    if context is None:
        return False

    text_content = render_to_string("emails/cellar_summary.txt", context=context)
    subject = f"{context['period_label']} {context['app_name']} Summary"
    EmailMultiAlternatives(subject, text_content, to=[user.email]).send()
    return True


def send_cellar_summary_emails(period: str = "weekly") -> int:
    User = get_user_model()
    users = (
        User.objects.exclude(user_settings__notifications=False)
        .exclude(email__isnull=True)
        .exclude(email="")
    )

    sent = 0
    for user in users:
        if send_cellar_summary_email(user, period=period):
            sent += 1
            logger.info(
                "Sent %s cellar summary to %s",
                period,
                user.email or user.username,
            )
    return sent


def _build_wine_summary_context(user, household, period: str):
    from wine_cellar.apps.storage.models import StorageItem
    from wine_cellar.apps.wine.models import (
        DrinkRecord,
        ReorderReminder,
        Wine,
        Wishlist,
    )

    today = date.today()
    user_settings = get_user_settings(user)
    currency_symbol = settings.CURRENCY_SYMBOLS.get(
        getattr(user_settings, "currency", "EUR"), "€"
    )

    total_value = StorageItem.objects.filter(
        household=household, deleted=False, wine__deleted=False
    ).aggregate(total=Sum(Coalesce("price", "wine__price"))).get("total") or Decimal(
        "0"
    )
    bottles_in_stock = StorageItem.objects.filter(
        household=household,
        deleted=False,
        wine__deleted=False,
    ).count()
    low_stock_count = (
        ReorderReminder.objects.filter(household=household, is_active=True)
        .annotate(
            current_stock=Count(
                "wine__storageitem",
                filter=Q(wine__storageitem__deleted=False),
            )
        )
        .filter(current_stock__lte=F("min_stock"))
        .count()
    )
    drink_stats = DrinkRecord.objects.filter(household=household).aggregate(
        total_consumed=Count("id"),
        avg_rating=Avg("rating", filter=Q(rating__isnull=False)),
    )
    wishlist_count = Wishlist.objects.filter(
        household=household,
        purchased=False,
    ).count()
    tracked_wines = Wine.objects.filter(household=household, deleted=False).count()
    upcoming_wines = (
        Wine.objects.filter(
            household=household,
            deleted=False,
            drink_to__isnull=False,
            drink_to__gt=0,
            drink_to__gte=today.year,
            drink_to__lte=today.year + 1,
            storageitem__deleted=False,
        )
        .distinct()
        .order_by("drink_to", "name")
    )
    overdue_count = (
        Wine.objects.filter(
            household=household,
            deleted=False,
            drink_to__isnull=False,
            drink_to__gt=0,
            drink_to__lt=today.year,
            storageitem__deleted=False,
        )
        .distinct()
        .count()
    )

    context = _base_context(
        user=user,
        household=household,
        app_name="Wine Cellar",
        period=period,
        total_items_label="Wines tracked",
        total_items=tracked_wines,
        total_value=_format_currency(total_value, currency_symbol),
        bottles_in_stock=bottles_in_stock,
        low_stock_count=low_stock_count,
        total_consumed=drink_stats["total_consumed"],
        avg_rating=drink_stats["avg_rating"],
        wishlist_count=wishlist_count,
    )
    context.update(
        {
            "highlight_title": "Upcoming drinking windows",
            "highlight_count": upcoming_wines.count(),
            "highlights": [
                {
                    "name": str(wine),
                    "detail": f"Drink by {wine.drink_to}",
                    "url": _absolute_url(wine.get_absolute_url()),
                }
                for wine in upcoming_wines[:5]
            ],
            "extra_stats": [
                {"label": "Overdue bottles", "value": overdue_count},
            ],
        }
    )
    return context


def _build_whisky_summary_context(user, household, period: str):
    from wine_cellar.apps.whisky.models import (
        FillLevel,
        Whisky,
        WhiskyDrinkingWindowAlert,
        WhiskyDrinkRecord,
        WhiskyReorderReminder,
        WhiskyStorageItem,
        WhiskyWishlist,
    )

    today = date.today()
    user_settings = get_user_settings(user)
    currency_symbol = settings.CURRENCY_SYMBOLS.get(
        getattr(user_settings, "currency", "EUR"), "€"
    )

    total_value = WhiskyStorageItem.objects.filter(
        household=household,
        deleted=False,
        whisky__deleted=False,
    ).aggregate(total=Sum(Coalesce("price", "whisky__price"))).get("total") or Decimal(
        "0"
    )
    bottles_in_stock = WhiskyStorageItem.objects.filter(
        household=household,
        deleted=False,
        whisky__deleted=False,
    ).count()
    low_stock_count = (
        WhiskyReorderReminder.objects.filter(household=household, is_active=True)
        .annotate(
            current_stock=Count(
                "whisky__whiskystorageitem",
                filter=Q(whisky__whiskystorageitem__deleted=False),
            )
        )
        .filter(current_stock__lte=F("min_stock"))
        .count()
    )
    drink_stats = WhiskyDrinkRecord.objects.filter(household=household).aggregate(
        total_consumed=Count("id"),
        avg_rating=Avg("rating", filter=Q(rating__isnull=False)),
    )
    wishlist_count = WhiskyWishlist.objects.filter(
        household=household,
        purchased=False,
    ).count()
    tracked_whiskies = Whisky.objects.filter(household=household, deleted=False).count()
    open_bottles = (
        WhiskyStorageItem.objects.filter(household=household, deleted=False)
        .exclude(fill_level=FillLevel.UNOPENED)
        .count()
    )

    dreg_cutoff_warning = today - timedelta(days=335)
    dreg_cutoff_expired = today - timedelta(days=365)
    dreg_warning_count = WhiskyStorageItem.objects.filter(
        household=household,
        deleted=False,
        fill_level=FillLevel.DREG,
        dreg_date__lte=dreg_cutoff_warning,
        dreg_date__gt=dreg_cutoff_expired,
    ).count()
    dreg_expired_count = WhiskyStorageItem.objects.filter(
        household=household,
        deleted=False,
        fill_level=FillLevel.DREG,
        dreg_date__lte=dreg_cutoff_expired,
    ).count()
    alert_cutoff = today + timedelta(days=SUMMARY_PERIODS[period])
    upcoming_alerts = WhiskyDrinkingWindowAlert.objects.filter(
        household=household,
        is_read=False,
        alert_date__gte=today,
        alert_date__lte=alert_cutoff,
    ).select_related("whisky")

    context = _base_context(
        user=user,
        household=household,
        app_name="Whisky Cabinet",
        period=period,
        total_items_label="Whiskies tracked",
        total_items=tracked_whiskies,
        total_value=_format_currency(total_value, currency_symbol),
        bottles_in_stock=bottles_in_stock,
        low_stock_count=low_stock_count,
        total_consumed=drink_stats["total_consumed"],
        avg_rating=drink_stats["avg_rating"],
        wishlist_count=wishlist_count,
    )
    context.update(
        {
            "highlight_title": "Upcoming drinking window alerts",
            "highlight_count": upcoming_alerts.count(),
            "highlights": [
                {
                    "name": str(alert.whisky),
                    "detail": f"{alert.alert_date}: {alert.message}",
                    "url": _absolute_url("/alerts/"),
                }
                for alert in upcoming_alerts.order_by("alert_date", "whisky__name")[:5]
            ],
            "extra_stats": [
                {"label": "Open bottles", "value": open_bottles},
                {"label": "Dreg warnings", "value": dreg_warning_count},
                {"label": "Expired dregs", "value": dreg_expired_count},
            ],
        }
    )
    return context
