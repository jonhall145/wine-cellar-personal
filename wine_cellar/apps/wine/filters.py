from datetime import date

import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django_filters import ChoiceFilter, OrderingFilter

from wine_cellar.apps.core.filters import (
    BeverageFilterMixin,
    get_collection_choices,
    get_country_choices_cached,
    get_related_model_choices_cached,
)
from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.wine.forms import WineFilterForm
from wine_cellar.apps.wine.models import Appellation, Collection, Wine


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
        extra_choices=[("missing", _("Missing"))],
    )


class WineFilter(BeverageFilterMixin, django_filters.FilterSet):
    storage_item_reverse = "storageitem"
    nullable_order_fields = ("vintage", "effective_price", "drink_to")
    search_fields = (
        "name",
        "comment",
        "subregion",
        "drinkrecord__tasting_notes",
        "storageitem__notes__note",
    )

    search = django_filters.CharFilter(
        method="filter_search", label=_("Search")
    )
    stock = ChoiceFilter(
        method="filter_has_stock",
        label=_("Show only in stock"),
        choices=((0, _("No")), (1, _("Yes"))),
        empty_label=None,
        null_label=None,
    )
    country = ChoiceFilter(
        choices=[],
        label=_("Country"),
    )
    appellation = ChoiceFilter(
        choices=[],
        label=_("Appellation"),
        method="filter_appellation",
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
    ready_to_drink = ChoiceFilter(
        method="filter_ready_to_drink",
        label=_("Ready to Drink"),
        choices=(
            ("", _("Any")),
            (0, _("No")),
            (1, _("Yes")),
        ),
    )
    has_window = ChoiceFilter(
        method="filter_has_window",
        label=_("Has Drink Window"),
        choices=(
            ("", _("Any")),
            (0, _("No")),
            (1, _("Yes")),
        ),
    )
    is_cold = ChoiceFilter(
        method="filter_is_cold",
        label=_("Cold Storage"),
        choices=(("", _("Any")), (0, _("No")), (1, _("Yes"))),
    )
    collection = ChoiceFilter(
        choices=[],
        label=_("Collection"),
        method="filter_collection",
    )
    order = OrderingFilter(
        choices=(
            ("-created", _("Recently Added")),
            ("created", _("Least Recently Added")),
            ("-name", _("Name Descending")),
            ("name", _("Name Ascending")),
            ("-vintage", _("Youngest First")),
            ("vintage", _("Oldest First")),
            ("drink_to", _("Drink Until")),
            ("-effective_price", _("Highest Price (Avg)")),
            ("effective_price", _("Lowest Price (Avg)")),
        ),
        label=_("Sorting"),
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
