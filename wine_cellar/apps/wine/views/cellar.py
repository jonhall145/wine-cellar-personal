from collections import defaultdict

from wine_cellar.apps.core.views import (
    BaseCellarValueView,
    BaseConsumptionStatsView,
    BaseStatsDashboardView,
)
from wine_cellar.apps.storage.models import StorageItem
from wine_cellar.apps.wine.models import DrinkRecord


class CellarValueView(BaseCellarValueView):
    template_name = "core/cellar_value.html"
    storage_item_model = StorageItem
    price_fallback_path = "wine__price"
    beverage_fk_name = "wine"
    select_related_fields = ("wine",)
    group_label = "Country"

    def get_groupings(self, item):
        return {
            "by_group": item.wine.country_name if item.wine.country else "Unknown",
            "by_type": item.wine.get_type if item.wine.wine_type else "Unknown",
        }


class ConsumptionStatsView(BaseConsumptionStatsView):
    template_name = "core/consumption_stats.html"
    drink_record_model = DrinkRecord
    beverage_fk_name = "wine"
    select_related_fields = ("wine",)
    group_label = "Country"

    def get_type_display(self, beverage):
        return beverage.get_type if beverage.wine_type else "Unknown"

    def get_secondary_stats(self, records):
        by_country = defaultdict(int)
        for record in records:
            country = record.wine.country_name if record.wine.country else "Unknown"
            by_country[country] += 1
        return {"by_group": dict(by_country)}


class StatsDashboardView(BaseStatsDashboardView):
    template_name = "core/stats_dashboard.html"
    storage_item_model = StorageItem
    beverage_fk_name = "wine"
    price_fallback_path = "wine__price"
    select_related_fields = ("wine",)

    def get_type_display(self, beverage):
        return beverage.get_type if beverage.wine_type else "Unknown"

    def get_country_name(self, beverage):
        return beverage.country_name if beverage.country else "Unknown"
