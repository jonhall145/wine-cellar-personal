import logging

from django.db.models import Count, Max, Min, Q

from wine_cellar.apps.core.views import BaseHomePageView
from wine_cellar.apps.storage.models import StorageItem
from wine_cellar.apps.wine.models import Wine

logger = logging.getLogger(__name__)


class HomePageView(BaseHomePageView):
    template_name = "core/homepage.html"
    beverage_model = Wine
    storage_item_model = StorageItem
    drink_record_model = None  # Lazy-loaded in get_app_specific_context
    wishlist_model = None
    reminder_model = None
    beverage_fk_name = "wine"
    beverage_price_path = "wine__price"
    stock_reverse_path = "wine__storageitem"
    homepage_title = "My Wine Cellar"
    stats_template = "includes/homepage_stats.html"
    alerts_template = "includes/homepage_alerts.html"
    beverage_icon = "wine-glass"

    def get_context_data(self, **kwargs):
        from wine_cellar.apps.wine.models import DrinkRecord, ReorderReminder, Wishlist

        self.drink_record_model = DrinkRecord
        self.wishlist_model = Wishlist
        self.reminder_model = ReorderReminder
        return super().get_context_data(**kwargs)

    def get_app_specific_context(self, household, user):
        from datetime import date

        from django.core.cache import cache

        cache_key = f"homepage_stats_{household.pk}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        wines = Wine.objects.filter(household=household).count()
        wine_stats = Wine.objects.filter(household=household).aggregate(
            wines_in_stock=Count(
                "id", filter=Q(storageitem__deleted=False), distinct=True
            ),
            countries=Count("country", distinct=True),
            oldest_vintage=Min("vintage", filter=Q(vintage__isnull=False)),
            youngest_vintage=Max("vintage", filter=Q(vintage__isnull=False)),
            overdue_count=Count(
                "id",
                filter=Q(
                    drink_to__isnull=False,
                    drink_to__gt=0,
                    drink_to__lt=date.today().year,
                    storageitem__deleted=False,
                ),
                distinct=True,
            ),
            upcoming_count=Count(
                "id",
                filter=Q(
                    drink_to__isnull=False,
                    drink_to__gt=0,
                    drink_to__gte=date.today().year,
                    drink_to__lte=date.today().year + 1,
                    storageitem__deleted=False,
                ),
                distinct=True,
            ),
        )

        # Pending hardware position reviews
        pending_reviews_count = 0
        try:
            from wine_cellar.apps.hardware.models import (
                PositionChangeReview,
                ReviewStatus,
            )

            pending_reviews_count = PositionChangeReview.objects.filter(
                household=household,
                status=ReviewStatus.PENDING,
            ).count()
        except Exception:
            pass

        result = {
            "wines": wines,
            "wines_in_stock": wine_stats["wines_in_stock"],
            "countries": wine_stats["countries"],
            "oldest": wine_stats["oldest_vintage"] or "-",
            "youngest": wine_stats["youngest_vintage"] or "-",
            "overdue_count": wine_stats["overdue_count"],
            "upcoming_count": wine_stats["upcoming_count"],
            "pending_reviews_count": pending_reviews_count,
        }
        cache.set(cache_key, result, 300)  # 5 minutes
        return result
