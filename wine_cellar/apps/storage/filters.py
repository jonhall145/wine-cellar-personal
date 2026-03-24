import django_filters
from django.db.models import Q
from django_filters import ChoiceFilter, OrderingFilter

from wine_cellar.apps.storage.models import Storage, StorageItem, get_app_type


class StorageItemFilter(django_filters.FilterSet):
    """Filter for the bottles list page."""

    wine_name = django_filters.CharFilter(
        field_name="wine__name",
        lookup_expr="icontains",
        label="Wine Name",
    )
    storage = django_filters.ModelChoiceFilter(
        queryset=Storage.objects.none(),
        label="Storage",
    )
    is_gift = ChoiceFilter(
        choices=(("", "All"), (True, "Yes"), (False, "No")),
        label="Is Gift",
    )
    has_occasion = ChoiceFilter(
        method="filter_has_occasion",
        choices=(("", "All"), ("1", "Yes"), ("0", "No")),
        label="Has Occasion",
    )
    show_used = ChoiceFilter(
        method="filter_show_used",
        choices=(("", "In stock only"), ("1", "Show all (incl. finished)")),
        label="Show used",
    )
    order = OrderingFilter(
        choices=(
            ("-created", "Recently Added"),
            ("created", "Oldest First"),
            ("wine__name", "Wine Name A-Z"),
            ("-wine__name", "Wine Name Z-A"),
            ("storage__name", "Storage A-Z"),
            ("-price", "Highest Price"),
            ("price", "Lowest Price"),
        ),
        label="Sort By",
        empty_label=None,
    )

    def filter_show_used(self, queryset, name, value):
        if value == "1":
            return queryset
        return queryset.filter(deleted=False)

    def filter_has_occasion(self, queryset, name, value):
        if value == "1":
            return queryset.exclude(occasion__isnull=True).exclude(occasion="")
        elif value == "0":
            return queryset.filter(Q(occasion__isnull=True) | Q(occasion=""))
        return queryset

    class Meta:
        model = StorageItem
        fields = ["wine_name", "storage", "is_gift", "has_occasion"]

    def __init__(self, data=None, queryset=None, *, request=None, prefix=None):
        super().__init__(data, queryset, request=request, prefix=prefix)
        if request and request.user.is_authenticated:
            self.filters["storage"].queryset = Storage.objects.filter(
                user=request.user, app_type=get_app_type()
            ).order_by("order", "created")
