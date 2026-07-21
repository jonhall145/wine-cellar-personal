import django_filters
from django_filters import ChoiceFilter, MultipleChoiceFilter, OrderingFilter

from wine_cellar.apps.core.filters import (
    BaseStockItemFilter,
    BeverageFilterMixin,
    get_collection_choices,
    get_country_choices_cached,
    get_related_model_choices_cached,
    get_stock_ordering_choices,
)
from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.whisky.forms import WhiskyFilterForm, WhiskyStorageItemFilterForm
from wine_cellar.apps.whisky.models import (
    WHISKY_COUNTRIES,
    Collection,
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
    nullable_order_fields = ("age_statement", "effective_price", "stock_first_added_at")
    order_field_aliases = {
        "created": "stock_first_added_at",
        "-created": "-stock_first_added_at",
    }
    search_fields = (
        "name",
        "comment",
        "cask_type",
        "bottler_series",
        "whiskydrinkrecord__tasting_notes",
        "whiskystorageitem__notes__note",
    )

    search = django_filters.CharFilter(method="filter_search", label="Search")

    whisky_type = ChoiceFilter(
        choices=[("", "Any")] + list(WhiskyType.choices),
        label="Type",
    )

    distillery = ChoiceFilter(
        choices=[],
        label="Distillery",
        method="filter_distillery",
    )

    region = ChoiceFilter(
        choices=[],
        label="Region",
        method="filter_region",
    )

    country = ChoiceFilter(
        choices=[],
        label="Country",
    )
    collection = ChoiceFilter(
        choices=[],
        label="Collection",
        method="filter_collection",
    )

    peated_level = ChoiceFilter(
        choices=[("", "Any")] + list(PeatedLevel.choices),
        label="Peated",
    )

    has_stock = ChoiceFilter(
        method="filter_has_stock",
        label="Show only in stock",
        choices=((0, "No"), (1, "Yes")),
        empty_label=None,
        null_label=None,
    )

    abv_min = django_filters.NumberFilter(
        field_name="abv", lookup_expr="gte", label="ABV Min"
    )
    abv_max = django_filters.NumberFilter(
        field_name="abv", lookup_expr="lte", label="ABV Max"
    )

    age_min = django_filters.NumberFilter(
        field_name="age_statement", lookup_expr="gte", label="Age Min"
    )
    age_max = django_filters.NumberFilter(
        field_name="age_statement", lookup_expr="lte", label="Age Max"
    )

    is_nas = ChoiceFilter(
        method="filter_is_nas",
        label="NAS (No Age Statement)",
        choices=(("", "Any"), (0, "No"), (1, "Yes")),
    )

    is_ob = ChoiceFilter(
        method="filter_is_ob",
        label="Official Bottling",
        choices=(("", "Any"), (0, "No (IB)"), (1, "Yes (OB)")),
    )

    owner = ChoiceFilter(
        choices=[],
        label="Owner",
    )

    rating = MultipleChoiceFilter(
        method="filter_rating",
        label="Rating",
        choices=(
            ("", "Any"),
            (0, "0 Stars"),
            (1, "1 Star"),
            (2, "2 Stars"),
            (3, "3 Stars"),
        ),
    )

    order = OrderingFilter(
        choices=(
            ("-created", "Recently Added"),
            ("created", "Least Recently Added"),
            ("-name", "Name Descending"),
            ("name", "Name Ascending"),
            ("-age_statement", "Oldest Age Statement"),
            ("age_statement", "Youngest Age Statement"),
            ("-abv", "Highest ABV"),
            ("abv", "Lowest ABV"),
            ("-effective_price", "Highest Price (Avg)"),
            ("effective_price", "Lowest Price (Avg)"),
        ),
        label="Sorting",
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

    def filter_collection(self, queryset, name, value):
        if value:
            return queryset.filter(collections__pk=int(value)).distinct()
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
        form = WhiskyFilterForm
        model = Whisky
        fields = [
            "search",
            "whisky_type",
            "distillery",
            "region",
            "country",
            "collection",
            "peated_level",
            "has_stock",
            "abv_min",
            "abv_max",
            "age_min",
            "age_max",
            "is_nas",
            "is_ob",
            "owner",
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
        self.filters["collection"].extra["choices"] = get_collection_choices(
            user, collection_model=Collection
        )

        if user and user.is_authenticated:
            household = get_active_household(user)
            if household:
                owner_values = list(
                    Whisky.objects.filter(household=household)
                    .exclude(owner="")
                    .values_list("owner", flat=True)
                    .distinct()
                    .order_by("owner")
                )
                if owner_values:
                    self.filters["owner"].extra["choices"] = [("", "Any")] + [
                        (v, v) for v in owner_values
                    ]


class WhiskyStorageItemFilter(BaseStockItemFilter):
    """Filter for the whisky bottles list page."""

    whisky_name = django_filters.CharFilter(
        field_name="whisky__name",
        lookup_expr="icontains",
        label="Whisky Name",
    )
    fill_level = MultipleChoiceFilter(
        choices=list(FillLevel.choices),
        label="Fill Level",
    )
    is_gift = ChoiceFilter(
        method="filter_is_gift",
        choices=(("", "All"), ("1", "Yes"), ("0", "No")),
        label="Is Gift",
    )
    owner = ChoiceFilter(
        choices=[],
        label="Owner",
    )
    order = OrderingFilter(
        choices=get_stock_ordering_choices("whisky__name", "Whisky"),
        label="Sort By",
        empty_label=None,
    )

    def filter_is_gift(self, queryset, name, value):
        if value == "1":
            return queryset.filter(is_gift=True)
        if value == "0":
            return queryset.filter(is_gift=False)
        return queryset

    class Meta:
        form = WhiskyStorageItemFilterForm
        model = WhiskyStorageItem
        fields = [
            "whisky_name",
            "storage",
            "fill_level",
            "is_gift",
            "has_occasion",
            "owner",
        ]

    def __init__(self, data=None, queryset=None, *, request=None, prefix=None):
        super().__init__(data, queryset, request=request, prefix=prefix)
        if request and request.user.is_authenticated:
            household = get_active_household(request.user)
            if household:
                owner_values = list(
                    WhiskyStorageItem.objects.filter(household=household)
                    .exclude(owner="")
                    .values_list("owner", flat=True)
                    .distinct()
                    .order_by("owner")
                )
                if owner_values:
                    self.filters["owner"].extra["choices"] = [("", "Any")] + [
                        (v, v) for v in owner_values
                    ]
