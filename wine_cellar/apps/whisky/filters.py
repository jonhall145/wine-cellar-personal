import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django_filters import ChoiceFilter, OrderingFilter

from wine_cellar.apps.core.filters import (
    BeverageFilterMixin,
    get_country_choices_cached,
    get_related_model_choices_cached,
)
from wine_cellar.apps.storage.models import Storage, get_app_type
from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.whisky.models import (
    WHISKY_COUNTRIES,
    Distillery,
    FillLevel,
    PeatedLevel,
    Whisky,
    WhiskyRegion,
    WhiskyStorageItem,
    WhiskyType,
)


def get_distillery_choices(user=None):
    """Build distillery choices for filter dropdown."""
    return get_related_model_choices_cached(
        user,
        cache_key_prefix="whisky_distillery_choices",
        related_model=Distillery,
        beverage_fk_path="whisky",
        storage_item_reverse="whiskystorageitem",
    )


def get_region_choices(user=None):
    """Build region choices for filter dropdown."""
    return get_related_model_choices_cached(
        user,
        cache_key_prefix="whisky_region_choices",
        related_model=WhiskyRegion,
        beverage_fk_path="whisky",
        storage_item_reverse="whiskystorageitem",
        order_by=("order", "name"),
    )


def get_country_choices(user=None):
    """Whisky-specific country choices with Scotland/Ireland/Japan favourites."""
    return get_country_choices_cached(
        user,
        cache_key_prefix="whisky_country_choices",
        beverage_model=Whisky,
        storage_item_reverse="whiskystorageitem",
        default_favourites=["XS", "IE", "JP", "US", "XE", "XW"],
        extra_countries=WHISKY_COUNTRIES,
        include_most_frequent=False,
    )


class WhiskyFilter(BeverageFilterMixin, django_filters.FilterSet):
    storage_item_reverse = "whiskystorageitem"
    nullable_order_fields = ("age_statement", "effective_price")

    name = django_filters.CharFilter(field_name="name", lookup_expr="icontains")

    whisky_type = ChoiceFilter(
        choices=[("", _("Any"))] + list(WhiskyType.choices),
        label=_("Type"),
    )

    distillery = ChoiceFilter(
        choices=[],
        label=_("Distillery"),
        method="filter_distillery",
    )

    region = ChoiceFilter(
        choices=[],
        label=_("Region"),
        method="filter_region",
    )

    country = ChoiceFilter(
        choices=[],
        label=_("Country"),
    )

    peated_level = ChoiceFilter(
        choices=[("", _("Any"))] + list(PeatedLevel.choices),
        label=_("Peated"),
    )

    has_stock = ChoiceFilter(
        method="filter_has_stock",
        label=_("Show only in stock"),
        choices=((0, _("No")), (1, _("Yes"))),
        empty_label=None,
        null_label=None,
    )

    abv_min = django_filters.NumberFilter(
        field_name="abv", lookup_expr="gte", label=_("ABV Min")
    )
    abv_max = django_filters.NumberFilter(
        field_name="abv", lookup_expr="lte", label=_("ABV Max")
    )

    age_min = django_filters.NumberFilter(
        field_name="age_statement", lookup_expr="gte", label=_("Age Min")
    )
    age_max = django_filters.NumberFilter(
        field_name="age_statement", lookup_expr="lte", label=_("Age Max")
    )

    is_nas = ChoiceFilter(
        method="filter_is_nas",
        label=_("NAS (No Age Statement)"),
        choices=(("", _("Any")), (0, _("No")), (1, _("Yes"))),
    )

    is_ob = ChoiceFilter(
        method="filter_is_ob",
        label=_("Official Bottling"),
        choices=(("", _("Any")), (0, _("No (IB)")), (1, _("Yes (OB)"))),
    )

    rating = ChoiceFilter(
        method="filter_rating",
        label=_("Rating"),
        choices=(
            ("", _("Any")),
            (0, _("0 Stars")),
            (1, _("1 Star")),
            (2, _("2 Stars")),
            (3, _("3 Stars")),
        ),
    )

    order = OrderingFilter(
        choices=(
            ("-created", _("Recently Added")),
            ("created", _("Least Recently Added")),
            ("-name", _("Name Descending")),
            ("name", _("Name Ascending")),
            ("-age_statement", _("Oldest Age Statement")),
            ("age_statement", _("Youngest Age Statement")),
            ("-abv", _("Highest ABV")),
            ("abv", _("Lowest ABV")),
            ("-effective_price", _("Highest Price (Avg)")),
            ("effective_price", _("Lowest Price (Avg)")),
        ),
        label=_("Sorting"),
        empty_label=None,
        null_label=None,
        method="filter_order",
    )

    def filter_distillery(self, queryset, name, value):
        if value:
            return queryset.filter(distillery_id=int(value))
        return queryset

    def filter_region(self, queryset, name, value):
        if value:
            return queryset.filter(region_id=int(value))
        return queryset

    def filter_is_nas(self, queryset, name, value):
        if value == "1":
            return queryset.filter(age_statement__isnull=True)
        elif value == "0":
            return queryset.filter(age_statement__isnull=False)
        return queryset

    def filter_is_ob(self, queryset, name, value):
        if value == "1":
            # Official bottling - no bottler set
            return queryset.filter(bottler__isnull=True)
        elif value == "0":
            # Independent bottling - bottler is set
            return queryset.filter(bottler__isnull=False)
        return queryset

    class Meta:
        model = Whisky
        fields = [
            "name",
            "whisky_type",
            "distillery",
            "region",
            "country",
            "peated_level",
            "has_stock",
            "abv_min",
            "abv_max",
            "age_min",
            "age_max",
            "is_nas",
            "is_ob",
            "rating",
        ]

    def __init__(self, data=None, queryset=None, *, request=None, prefix=None):
        super().__init__(data, queryset, request=request, prefix=prefix)
        user = request.user if request else None

        # Update distillery filter with choices from user's whiskies
        self.filters["distillery"].extra["choices"] = get_distillery_choices(user)

        # Update region filter with choices from user's whiskies
        self.filters["region"].extra["choices"] = get_region_choices(user)

        # Update country filter with favourites-ordered choices
        self.filters["country"].extra["choices"] = get_country_choices(user)


class WhiskyStorageItemFilter(django_filters.FilterSet):
    """Filter for the whisky bottles list page."""

    whisky_name = django_filters.CharFilter(
        field_name="whisky__name",
        lookup_expr="icontains",
        label=_("Whisky Name"),
    )
    storage = django_filters.ModelChoiceFilter(
        queryset=Storage.objects.none(),
        label=_("Storage"),
    )
    fill_level = ChoiceFilter(
        choices=[("", _("All"))] + list(FillLevel.choices),
        label=_("Fill Level"),
    )
    is_gift = ChoiceFilter(
        method="filter_is_gift",
        choices=(("", _("All")), ("1", _("Yes")), ("0", _("No"))),
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
            ("whisky__name", _("Whisky Name A-Z")),
            ("-whisky__name", _("Whisky Name Z-A")),
            ("storage__name", _("Storage A-Z")),
            ("-price", _("Highest Price")),
            ("price", _("Lowest Price")),
        ),
        label=_("Sort By"),
        empty_label=None,
    )

    def filter_is_gift(self, queryset, name, value):
        if value == "1":
            return queryset.filter(is_gift=True)
        if value == "0":
            return queryset.filter(is_gift=False)
        return queryset

    def filter_has_occasion(self, queryset, name, value):
        if value == "1":
            return queryset.exclude(occasion__isnull=True).exclude(occasion="")
        if value == "0":
            return queryset.filter(Q(occasion__isnull=True) | Q(occasion=""))
        return queryset

    class Meta:
        model = WhiskyStorageItem
        fields = ["whisky_name", "storage", "fill_level", "is_gift", "has_occasion"]

    def __init__(self, data=None, queryset=None, *, request=None, prefix=None):
        super().__init__(data, queryset, request=request, prefix=prefix)
        if request and request.user.is_authenticated:
            household = get_active_household(request.user)
            if household:
                self.filters["storage"].queryset = Storage.objects.filter(
                    household=household,
                    app_type=get_app_type(),
                ).order_by("order", "created")
