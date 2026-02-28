import pycountry
from django.core.cache import cache
from django.db.models import Count, F, Q
from django.utils.translation import gettext_lazy as _

from wine_cellar.apps.user.views import get_active_household

# Cache timeout for filter choices (5 minutes)
FILTER_CACHE_TIMEOUT = 300


class BeverageFilterMixin:
    """Shared filter methods for wine and whisky FilterSets.

    Subclasses must set:
        storage_item_reverse: str  — e.g. "storageitem" or "whiskystorageitem"
        nullable_order_fields: tuple — e.g. ("vintage", "effective_price")
    """

    storage_item_reverse = None
    nullable_order_fields = ()

    def filter_rating(self, queryset, name, value):
        if value == "0":
            return queryset.filter(Q(rating=0) | Q(rating__isnull=True))
        if value:
            return queryset.filter(rating=int(value))
        return queryset

    def filter_order(self, queryset, name, value):
        """Custom ordering that puts NULLs at the end."""
        if not value:
            return queryset
        ordering = value[0] if isinstance(value, list) else value
        if ordering.lstrip("-") in self.nullable_order_fields:
            field = F(ordering.lstrip("-"))
            if ordering.startswith("-"):
                return queryset.order_by(field.desc(nulls_last=True))
            return queryset.order_by(field.asc(nulls_last=True))
        return queryset.order_by(ordering)

    def filter_has_stock(self, queryset, name, value):
        if value == "1":
            reverse = self.storage_item_reverse
            return queryset.filter(
                **{f"{reverse}__isnull": False, f"{reverse}__deleted": False}
            ).distinct()
        return queryset


def get_country_choices_cached(
    user=None,
    *,
    cache_key_prefix,
    beverage_model,
    storage_item_reverse,
    default_favourites,
    extra_countries=None,
    include_most_frequent=True,
):
    """Build country choices with favourites at the top.

    Only includes countries that have beverages in stock.
    Results are cached per-household for 5 minutes.

    Args:
        cache_key_prefix: e.g. "country_choices" or "whisky_country_choices"
        beverage_model: Wine or Whisky model class
        storage_item_reverse: e.g. "storageitem" or "whiskystorageitem"
        default_favourites: list of alpha_2 codes
        extra_countries: optional dict of custom country codes (e.g. whisky regions)
        include_most_frequent: whether to add the most frequent country to favourites
    """
    household = get_active_household(user) if user and user.is_authenticated else None
    household_id = household.id if household else "anon"
    cache_key = f"{cache_key_prefix}_{household_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    favourites = list(default_favourites)
    countries_in_stock = set()

    si_null = f"{storage_item_reverse}__isnull"
    si_del = f"{storage_item_reverse}__deleted"

    if household:
        countries_in_stock = set(
            beverage_model.objects.filter(
                household=household,
                **{si_null: False, si_del: False},
            )
            .values_list("country", flat=True)
            .distinct()
        )

        if include_most_frequent:
            most_frequent = (
                beverage_model.objects.filter(
                    household=household,
                    **{si_null: False, si_del: False},
                )
                .values("country")
                .annotate(count=Count("id"))
                .order_by("-count")
                .first()
            )
            if most_frequent and most_frequent["country"] not in favourites:
                favourites.insert(0, most_frequent["country"])

    all_countries = {c.alpha_2: c.name for c in pycountry.countries}
    if extra_countries:
        all_countries.update(extra_countries)

    favourite_choices = []
    other_choices = []

    for code in favourites:
        if code in all_countries and code in countries_in_stock:
            favourite_choices.append((code, all_countries[code]))

    for code, name in sorted(all_countries.items(), key=lambda x: x[1]):
        if code not in favourites and code in countries_in_stock:
            other_choices.append((code, name))

    choices = [("", _("Any"))]
    if favourite_choices and other_choices:
        choices += favourite_choices + [("---", "─" * 20)] + other_choices
    else:
        choices += favourite_choices + other_choices

    cache.set(cache_key, choices, FILTER_CACHE_TIMEOUT)
    return choices
