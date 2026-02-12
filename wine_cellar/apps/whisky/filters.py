import django_filters
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from django_filters import ChoiceFilter, OrderingFilter

from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.whisky.models import (
    Distillery,
    PeatedLevel,
    Whisky,
    WhiskyRegion,
    WhiskyType,
)

# Cache timeout for filter choices (5 minutes)
FILTER_CACHE_TIMEOUT = 300


def get_distillery_choices(user=None):
    """
    Build distillery choices for filter dropdown.
    Only includes distilleries that have whiskies in stock.
    Results are cached per-household for 5 minutes.
    """
    household = get_active_household(user) if user and user.is_authenticated else None
    household_id = household.id if household else "anon"
    cache_key = f"whisky_distillery_choices_{household_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    choices = [("", _("Any"))]

    if household:
        # Get distilleries that have whiskies in stock for this household
        distilleries_in_stock = (
            Distillery.objects.filter(
                whisky__household=household,
                whisky__whiskystorageitem__isnull=False,
                whisky__whiskystorageitem__deleted=False,
            )
            .distinct()
            .order_by("name")
        )

        for dist in distilleries_in_stock:
            choices.append((dist.pk, dist.name))

    cache.set(cache_key, choices, FILTER_CACHE_TIMEOUT)
    return choices


def get_region_choices(user=None):
    """
    Build region choices for filter dropdown.
    Only includes regions that have whiskies in stock.
    Results are cached per-household for 5 minutes.
    """
    household = get_active_household(user) if user and user.is_authenticated else None
    household_id = household.id if household else "anon"
    cache_key = f"whisky_region_choices_{household_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    choices = [("", _("Any"))]

    if household:
        # Get regions that have whiskies in stock for this household
        regions_in_stock = (
            WhiskyRegion.objects.filter(
                whisky__household=household,
                whisky__whiskystorageitem__isnull=False,
                whisky__whiskystorageitem__deleted=False,
            )
            .distinct()
            .order_by("order", "name")
        )

        for region in regions_in_stock:
            choices.append((region.pk, region.name))

    cache.set(cache_key, choices, FILTER_CACHE_TIMEOUT)
    return choices


class WhiskyFilter(django_filters.FilterSet):
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
        ),
        label=_("Sorting"),
        empty_label=None,
        null_label=None,
    )

    def filter_distillery(self, queryset, name, value):
        if value:
            return queryset.filter(distillery_id=int(value))
        return queryset

    def filter_region(self, queryset, name, value):
        if value:
            return queryset.filter(region_id=int(value))
        return queryset

    def filter_has_stock(self, queryset, name, value):
        if value == "1":
            return queryset.filter(
                whiskystorageitem__isnull=False, whiskystorageitem__deleted=False
            ).distinct()
        else:
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

    def filter_rating(self, queryset, name, value):
        if value:
            return queryset.filter(rating=int(value))
        return queryset

    class Meta:
        model = Whisky
        fields = [
            "name",
            "whisky_type",
            "distillery",
            "region",
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
