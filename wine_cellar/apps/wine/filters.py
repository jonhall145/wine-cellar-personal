from datetime import date

import django_filters
import pycountry
from django.core.cache import cache
from django.db.models import Count, F, Q
from django.utils.translation import gettext_lazy as _
from django_filters import ChoiceFilter, OrderingFilter

from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.wine.forms import WineFilterForm
from wine_cellar.apps.wine.models import Appellation, Wine

# Default favourite countries (alpha_2 codes)
DEFAULT_FAVOURITES = ["GB", "PT", "FR"]

# Cache timeout for filter choices (5 minutes)
FILTER_CACHE_TIMEOUT = 300


def get_country_choices_with_favourites(user=None):
    """
    Build country choices with favourites at the top.
    Only includes countries that have wines in stock.
    Favourites: UK, Portugal, France + most frequent from user's cellar.
    Results are cached per-household for 5 minutes.
    """
    household = get_active_household(user) if user and user.is_authenticated else None
    household_id = household.id if household else "anon"
    cache_key = f"country_choices_{household_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    favourites = list(DEFAULT_FAVOURITES)

    # Get countries that have wines in stock
    countries_in_stock = set()
    if household:
        countries_in_stock = set(
            Wine.objects.filter(
                household=household,
                storageitem__isnull=False,
                storageitem__deleted=False,
            )
            .values_list("country", flat=True)
            .distinct()
        )

        # Get most frequent country from household's wines in stock
        most_frequent = (
            Wine.objects.filter(
                household=household,
                storageitem__isnull=False,
                storageitem__deleted=False,
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

    # Return Any first, then favourites, then separator, then rest
    any_choice = [("", _("Any"))]
    if favourite_choices and other_choices:
        choices = any_choice + favourite_choices + [("---", "─" * 20)] + other_choices
    else:
        choices = any_choice + favourite_choices + other_choices

    cache.set(cache_key, choices, FILTER_CACHE_TIMEOUT)
    return choices


def get_appellation_choices(user=None):
    """
    Build appellation choices for filter dropdown.
    Only includes appellations that have wines in stock.
    Results are cached per-household for 5 minutes.
    """
    household = get_active_household(user) if user and user.is_authenticated else None
    household_id = household.id if household else "anon"
    cache_key = f"appellation_choices_{household_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    choices = [("", _("Any")), ("missing", _("Missing"))]

    if household:
        # Get appellations that have wines in stock for this household
        appellations_in_stock = (
            Appellation.objects.filter(
                wine__household=household,
                wine__storageitem__isnull=False,
                wine__storageitem__deleted=False,
            )
            .distinct()
            .order_by("country", "name")
        )

        for app in appellations_in_stock:
            choices.append((app.pk, f"{app.name} ({app.country})"))

    cache.set(cache_key, choices, FILTER_CACHE_TIMEOUT)
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

    def filter_order(self, queryset, name, value):
        """Custom ordering that puts NULLs at the end."""
        if not value:
            return queryset

        ordering = value[0] if isinstance(value, list) else value

        # Fields that can have NULLs need nulls_last to sort predictably
        if ordering.lstrip("-") in ("vintage", "effective_price"):
            field = F(ordering.lstrip("-"))
            if ordering.startswith("-"):
                return queryset.order_by(field.desc(nulls_last=True))
            return queryset.order_by(field.asc(nulls_last=True))
        else:
            return queryset.order_by(ordering)

    def filter_stock(self, queryset, name, value):
        if value == "1":
            return queryset.filter(
                storageitem__isnull=False, storageitem__deleted=False
            ).distinct()
        else:
            return queryset

    def filter_rating(self, queryset, name, value):
        if value == "0":
            return queryset.filter(Q(rating=0) | Q(rating__isnull=True))
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

    def filter_appellation(self, queryset, name, value):
        if value == "missing":
            return queryset.filter(appellation__isnull=True)
        elif value:
            return queryset.filter(appellation_id=int(value))
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
            "appellation",
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
