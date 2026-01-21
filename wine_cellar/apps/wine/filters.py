from datetime import date

import django_filters
import pycountry
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _
from django_filters import ChoiceFilter, OrderingFilter

from wine_cellar.apps.wine.forms import WineFilterForm
from wine_cellar.apps.wine.models import Wine

# Default favourite countries (alpha_2 codes)
DEFAULT_FAVOURITES = ["GB", "PT", "FR"]


def get_country_choices_with_favourites(user=None):
    """
    Build country choices with favourites at the top.
    Only includes countries that have wines in stock.
    Favourites: UK, Portugal, France + most frequent from user's cellar.
    """
    favourites = list(DEFAULT_FAVOURITES)

    # Get countries that have wines in stock
    countries_in_stock = set()
    if user and user.is_authenticated:
        countries_in_stock = set(
            Wine.objects.filter(
                user=user, storageitem__isnull=False, storageitem__deleted=False
            )
            .values_list("country", flat=True)
            .distinct()
        )

        # Get most frequent country from user's wines in stock
        most_frequent = (
            Wine.objects.filter(
                user=user, storageitem__isnull=False, storageitem__deleted=False
            )
            .values("country")
            .annotate(count=Count("id"))
            .order_by("-count")
            .first()
        )
        if most_frequent and most_frequent["country"] not in favourites:
            favourites.insert(0, most_frequent["country"])

    # Build choices list - only include countries with stock
    all_countries = {c.alpha_2: c.name for c in pycountry.countries}
    favourite_choices = []
    other_choices = []

    for code in favourites:
        if code in all_countries and code in countries_in_stock:
            favourite_choices.append((code, all_countries[code]))

    for code, name in sorted(all_countries.items(), key=lambda x: x[1]):
        if code not in favourites and code in countries_in_stock:
            other_choices.append((code, name))

    # Return favourites first, then separator (if both sections have items), then rest
    if favourite_choices and other_choices:
        choices = favourite_choices + [("", "─" * 20)] + other_choices
    else:
        choices = favourite_choices + other_choices
    return choices


class WineFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    stock = ChoiceFilter(
        method="filter_stock",
        label=_("Show only in stock"),
        choices=((0, _("No")), (1, _("Yes"))),
        empty_label=None,
        null_label=None,
    )
    country = ChoiceFilter(
        choices=[],
        label=_("Country"),
    )
    rating = ChoiceFilter(
        method="filter_rating",
        label=_("Rating"),
        choices=(
            (0, _("0 Stars")),
            (1, _("1 Star")),
            (2, _("2 Stars")),
            (3, _("3 Stars")),
        ),
        empty_label=_("Any"),
    )
    ready_to_drink = ChoiceFilter(
        method="filter_ready_to_drink",
        label=_("Ready to Drink"),
        choices=(
            (0, _("No")),
            (1, _("Yes")),
        ),
        empty_label=_("Any"),
    )
    has_window = ChoiceFilter(
        method="filter_has_window",
        label=_("Has Drink Window"),
        choices=(
            (0, _("No")),
            (1, _("Yes")),
        ),
        empty_label=_("Any"),
    )
    is_cold = ChoiceFilter(
        method="filter_is_cold",
        label=_("Cold Storage"),
        choices=((0, _("No")), (1, _("Yes"))),
        empty_label=_("Any"),
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
    )

    def filter_stock(self, queryset, name, value):
        if value == "1":
            return queryset.filter(
                storageitem__isnull=False, storageitem__deleted=False
            ).distinct()
        else:
            return queryset

    def filter_rating(self, queryset, name, value):
        if value:
            return queryset.filter(rating=int(value))
        return queryset

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

    class Meta:
        form = WineFilterForm
        model = Wine
        fields = [
            "name",
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
            "stock",
        ]

    def __init__(self, data=None, queryset=None, *, request=None, prefix=None):
        super().__init__(data, queryset, request=request, prefix=prefix)
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
            ].queryset.filter(Q(user=None) | Q(user=request.user))

        # Update country filter with favourites-ordered choices
        self.filters["country"].extra["choices"] = get_country_choices_with_favourites(
            request.user if request else None
        )
