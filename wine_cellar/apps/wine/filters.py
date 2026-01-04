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
    Favourites: UK, Portugal, France + most frequent from user's cellar.
    """
    favourites = list(DEFAULT_FAVOURITES)

    # Get most frequent country from user's wines in stock
    if user and user.is_authenticated:
        most_frequent = (
            Wine.objects.filter(
                user=user, storageitem__isnull=False, storageitem__deleted=False
            ).values("country")
            .annotate(count=Count("id"))
            .order_by("-count")
            .first()
        )
        if most_frequent and most_frequent["country"] not in favourites:
            favourites.insert(0, most_frequent["country"])

    # Build choices list
    all_countries = {c.alpha_2: c.name for c in pycountry.countries}
    favourite_choices = []
    other_choices = []

    for code in favourites:
        if code in all_countries:
            favourite_choices.append((code, all_countries[code]))

    for code, name in sorted(all_countries.items(), key=lambda x: x[1]):
        if code not in favourites:
            other_choices.append((code, name))

    # Return favourites first, then separator, then rest
    choices = favourite_choices + [("", "─" * 20)] + other_choices
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
    order = OrderingFilter(
        choices=(
            ("-created", _("Recently Added")),
            ("created", _("Least Recently Added")),
            ("-name", _("Name Descending")),
            ("name", _("Name Ascending")),
            ("-vintage", _("Youngest First")),
            ("vintage", _("Oldest First")),
            ("drink_by", _("Drink By")),
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

    class Meta:
        form = WineFilterForm
        model = Wine
        fields = [
            "name",
            "wine_type",
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
