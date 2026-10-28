import json
from datetime import date

import django_filters
from django.db.models import Count, Q
from django_filters import ChoiceFilter, MultipleChoiceFilter, OrderingFilter

from wine_cellar.apps.core.filters import (
    BeverageFilterMixin,
    get_collection_choices,
    get_country_choices_cached,
    get_related_model_choices_cached,
)
from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.wine.forms import WineFilterForm
from wine_cellar.apps.wine.models import Appellation, Collection, Grape, Wine, WineType


def get_country_choices_with_favourites(user=None):
    """Wine-specific country choices with UK/PT/FR favourites."""
    return get_country_choices_cached(
        user,
        cache_key_prefix="country_choices",
        beverage_model=Wine,
        storage_item_reverse="storageitem",
        default_favourites=["GB", "PT", "FR"],
    )


def get_appellation_choices(user=None):
    """Build appellation choices for filter dropdown."""
    return get_related_model_choices_cached(
        user,
        cache_key_prefix="appellation_choices",
        related_model=Appellation,
        beverage_fk_path="wine",
        storage_item_reverse="storageitem",
        order_by=("country", "name"),
        format_choice=lambda app: f"{app.name} ({app.country})",
        extra_choices=[("missing", "Missing")],
    )


def get_grape_queryset(user=None, *, selected_wine_types=None):
    """Order grape choices so relevant, in-stock grapes appear first."""
    household = get_active_household(user) if user and user.is_authenticated else None
    queryset = Grape.objects.filter(household__isnull=True).order_by("name")

    if not household:
        return queryset

    queryset = Grape.objects.filter(Q(household__isnull=True) | Q(household=household))
    held_wine_filter = Q(
        wine__household=household,
        wine__deleted=False,
        wine__storageitem__isnull=False,
        wine__storageitem__deleted=False,
    )
    matching_wine_filter = held_wine_filter
    if selected_wine_types:
        matching_wine_filter &= Q(wine__wine_type__in=selected_wine_types)

    return queryset.annotate(
        matching_wine_count=Count("wine", filter=matching_wine_filter, distinct=True),
        held_wine_count=Count("wine", filter=held_wine_filter, distinct=True),
    ).order_by("-matching_wine_count", "-held_wine_count", "name")


def get_grape_wine_type_map(user=None):
    """Map grape ids to the in-stock wine types they currently appear in."""
    household = get_active_household(user) if user and user.is_authenticated else None
    if not household:
        return {}

    grape_rows = (
        Grape.objects.filter(
            Q(household__isnull=True) | Q(household=household),
            wine__household=household,
            wine__deleted=False,
            wine__storageitem__isnull=False,
            wine__storageitem__deleted=False,
        )
        .values_list("pk", "wine__wine_type")
        .distinct()
    )

    grape_wine_types = {}
    for grape_id, wine_type in grape_rows:
        grape_wine_types.setdefault(str(grape_id), []).append(wine_type)
    return grape_wine_types


class WineFilter(BeverageFilterMixin, django_filters.FilterSet):
    storage_item_reverse = "storageitem"
    nullable_order_fields = (
        "vintage",
        "effective_price",
        "drink_to",
        "stock_first_added_at",
    )
    order_field_aliases = {
        "created": "stock_first_added_at",
        "-created": "-stock_first_added_at",
    }
    search_fields = (
        "name",
        "comment",
        "subregion",
        "drinkrecord__tasting_notes",
        "storageitem__notes__note",
    )
    include_unrated_with_zero_rating = True

    search = django_filters.CharFilter(method="filter_search", label="Search")
    stock = ChoiceFilter(
        method="filter_has_stock",
        label="Show only in stock",
        choices=((0, "No"), (1, "Yes")),
        empty_label=None,
        null_label=None,
    )
    country = ChoiceFilter(
        choices=[],
        label="Country",
    )
    appellation = ChoiceFilter(
        choices=[],
        label="Appellation",
        method="filter_appellation",
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
    ready_to_drink = ChoiceFilter(
        method="filter_ready_to_drink",
        label="Ready to Drink",
        choices=(
            ("", "Any"),
            (0, "No"),
            (1, "Yes"),
        ),
    )
    has_window = ChoiceFilter(
        method="filter_has_window",
        label="Has Drink Window",
        choices=(
            ("", "Any"),
            (0, "No"),
            (1, "Yes"),
        ),
    )
    is_cold = ChoiceFilter(
        method="filter_is_cold",
        label="Cold Storage",
        choices=(("", "Any"), (0, "No"), (1, "Yes")),
    )
    wine_type = django_filters.MultipleChoiceFilter(
        choices=WineType.choices,
        label="Type",
    )
    grapes = django_filters.ModelMultipleChoiceFilter(
        queryset=Grape.objects.none(),
        label="Grapes",
        method="filter_grapes",
    )
    collection = ChoiceFilter(
        choices=[],
        label="Collection",
        method="filter_collection",
    )
    order = OrderingFilter(
        choices=(
            ("-created", "Recently Added"),
            ("created", "Least Recently Added"),
            ("-name", "Name Descending"),
            ("name", "Name Ascending"),
            ("-vintage", "Youngest First"),
            ("vintage", "Oldest First"),
            ("drink_to", "Drink Until"),
            ("-effective_price", "Highest Price (Avg)"),
            ("effective_price", "Lowest Price (Avg)"),
        ),
        label="Sorting",
        empty_label=None,
        null_label=None,
        method="filter_order",
    )

    def filter_ready_to_drink(self, queryset, name, value):
        if not value:  # "Any" option selected
            return queryset

        current_year = date.today().year
        if value == "1":
            # Ready to drink: drink_from is 0 (now) or <= current year
            # AND drink_to is null or 0 (now) or >= current year
            return queryset.filter(
                Q(drink_from__isnull=True)
                | Q(drink_from=0)
                | Q(drink_from__lte=current_year)
            ).filter(
                Q(drink_to__isnull=True) | Q(drink_to=0) | Q(drink_to__gte=current_year)
            )
        elif value == "0":
            # Not ready: drink_from is set and > current year
            # OR drink_to is set and < current year (past its prime)
            return queryset.filter(
                Q(drink_from__gt=current_year)
                | Q(drink_to__lt=current_year, drink_to__gt=0)
            )
        return queryset

    def filter_has_window(self, queryset, name, value):
        if value == "1":
            # Has any drink window set (drink_from OR drink_to is not null)
            return queryset.filter(
                Q(drink_from__isnull=False) | Q(drink_to__isnull=False)
            )
        elif value == "0":
            # No drink window set
            return queryset.filter(drink_from__isnull=True, drink_to__isnull=True)
        return queryset

    def filter_is_cold(self, queryset, name, value):
        if value == "1":
            return queryset.filter(
                storageitem__deleted=False, storageitem__storage__is_cold=True
            ).distinct()
        elif value == "0":
            return queryset.filter(
                storageitem__deleted=False, storageitem__storage__is_cold=False
            ).distinct()
        return queryset

    def filter_appellation(self, queryset, name, value):
        if value == "missing":
            return queryset.filter(appellation__isnull=True)
        elif value:
            return queryset.filter(appellation_id=int(value))
        return queryset

    def filter_collection(self, queryset, name, value):
        if value:
            return queryset.filter(collections__pk=int(value)).distinct()
        return queryset

    def filter_grapes(self, queryset, name, value):
        if value:
            return queryset.filter(grapes__in=value).distinct()
        return queryset

    class Meta:
        form = WineFilterForm
        model = Wine
        fields = [
            "search",
            "wine_type",
            "rating",
            "ready_to_drink",
            "has_window",
            "is_cold",
            "attributes",
            "category",
            "vintage",
            "vineyard",
            "grapes",
            "food_pairings",
            "source",
            "country",
            "appellation",
            "collection",
            "stock",
        ]

    def __init__(self, data=None, queryset=None, *, request=None, prefix=None):
        super().__init__(data, queryset, request=request, prefix=prefix)
        user = request.user if request else None
        household = (
            get_active_household(user) if user and user.is_authenticated else None
        )
        selected_wine_types = []
        if data is not None:
            if hasattr(data, "getlist"):
                selected_wine_types = [
                    value for value in data.getlist("wine_type") if value
                ]
            else:
                wine_type_value = data.get("wine_type")
                if isinstance(wine_type_value, (list, tuple)):
                    selected_wine_types = [value for value in wine_type_value if value]
                elif wine_type_value:
                    selected_wine_types = [wine_type_value]
        user_filters = [
            "vineyard",
            "grapes",
            "food_pairings",
            "source",
            "attributes",
        ]
        for user_filter in user_filters:
            self.filters[user_filter].queryset = self.filters[
                user_filter
            ].queryset.filter(Q(household__isnull=True) | Q(household=household))

        grape_queryset = get_grape_queryset(
            user,
            selected_wine_types=selected_wine_types,
        )
        self.filters["grapes"].queryset = grape_queryset

        # Update country filter with favourites-ordered choices
        self.filters["country"].extra["choices"] = get_country_choices_with_favourites(
            request.user if request else None
        )

        # Update appellation filter with choices from user's wines
        self.filters["appellation"].extra["choices"] = get_appellation_choices(
            request.user if request else None
        )
        self.filters["collection"].extra["choices"] = get_collection_choices(
            request.user if request else None, collection_model=Collection
        )

        self.form.fields["grapes"].queryset = grape_queryset
        self.form.fields["grapes"].widget.attrs["data-grape-wine-types"] = json.dumps(
            get_grape_wine_type_map(user)
        )
