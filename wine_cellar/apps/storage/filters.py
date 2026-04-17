import django_filters
from django_filters import ChoiceFilter, OrderingFilter

from wine_cellar.apps.core.filters import (
    BaseStockItemFilter,
    get_stock_ordering_choices,
)
from wine_cellar.apps.storage.models import StorageItem


class StorageItemFilter(BaseStockItemFilter):
    """Filter for the bottles list page."""

    wine_name = django_filters.CharFilter(
        field_name="wine__name",
        lookup_expr="icontains",
        label="Wine Name",
    )
    is_gift = ChoiceFilter(
        choices=(("", "All"), (True, "Yes"), (False, "No")),
        label="Is Gift",
    )
    order = OrderingFilter(
        choices=get_stock_ordering_choices("wine__name", "Wine"),
        label="Sort By",
        empty_label=None,
    )

    class Meta:
        model = StorageItem
        fields = ["wine_name", "storage", "is_gift", "has_occasion"]
