import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django_filters import ChoiceFilter, OrderingFilter

from wine_cellar.apps.storage.models import Storage, StorageItem


class StorageItemFilter(django_filters.FilterSet):
    """Filter for the bottles list page."""

    wine_name = django_filters.CharFilter(
        field_name="wine__name",
        lookup_expr="icontains",
        label=_("Wine Name"),
    )
    storage = django_filters.ModelChoiceFilter(
        queryset=Storage.objects.none(),
        label=_("Storage"),
    )
    is_gift = ChoiceFilter(
        choices=(("", _("All")), (True, _("Yes")), (False, _("No"))),
        label=_("Is Gift"),
    )
    has_occasion = ChoiceFilter(
        method="filter_has_occasion",
        choices=(("", _("All")), ("1", _("Yes")), ("0", _("No"))),
        label=_("Has Occasion"),
    )
    order = OrderingFilter(
        choices=(
            ("-created", _("Recently Added")),
            ("created", _("Oldest First")),
            ("wine__name", _("Wine Name A-Z")),
            ("-wine__name", _("Wine Name Z-A")),
            ("storage__name", _("Storage A-Z")),
            ("-price", _("Highest Price")),
            ("price", _("Lowest Price")),
        ),
        label=_("Sort By"),
        empty_label=None,
    )

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
                user=request.user
            ).order_by("order", "created")
