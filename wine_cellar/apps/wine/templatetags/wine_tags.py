from datetime import date

from django import template
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

register = template.Library()


WINE_TYPE_CLASSES = {
    "WH": "white",
    "RE": "red",
    "RO": "rose",
    "SP": "sparkling",
    "DE": "dessert",
    "FO": "fortified",
    "OR": "orange",
}

WINE_TYPE_LABELS = {
    "WH": _("White"),
    "RE": _("Red"),
    "RO": _("Rosé"),
    "SP": _("Sparkling"),
    "DE": _("Dessert"),
    "FO": _("Fortified"),
    "OR": _("Orange"),
}


@register.filter
def wine_type_css(wine_type: str) -> str:
    """Return CSS class suffix for wine type (red, white, rose, etc.)."""
    return WINE_TYPE_CLASSES.get(wine_type, "")


@register.simple_tag
def wine_type_badge(wine_type: str) -> str:
    """Render a colored badge for the wine type."""
    if not wine_type:
        return ""

    css_class = WINE_TYPE_CLASSES.get(wine_type, "")
    label = WINE_TYPE_LABELS.get(wine_type, wine_type)

    if not css_class:
        return f'<span class="wine-type-badge">{label}</span>'

    return mark_safe(
        f'<span class="wine-type-badge wine-type-badge--{css_class}">{label}</span>'
    )


@register.simple_tag
def rating_stars(rating, max_rating=3):
    """Render star rating display (0-3 star scale)."""
    if rating is None:
        return mark_safe('<span class="rating-stars rating-stars--empty">—</span>')

    # Ensure rating is within bounds
    stars = min(int(rating), max_rating)

    html = '<span class="rating-stars">'

    # Full stars
    for _i in range(stars):
        html += (
            '<i class="fa-solid fa-star rating-stars__star '
            'rating-stars__star--filled"></i>'
        )

    # Empty stars
    for _j in range(max_rating - stars):
        html += '<i class="fa-regular fa-star rating-stars__star"></i>'

    html += "</span>"

    return mark_safe(html)


@register.simple_tag
def drink_window_indicator(drink_from, drink_to):
    """Show whether a wine is ready to drink, too young, or past its prime.

    Args:
        drink_from: Year to start drinking, or 0 for "now", or None
        drink_to: Year to drink by, or 0 for "now", or None
    """
    # Need at least one value to show anything
    if drink_from is None and drink_to is None:
        return ""

    current_year = date.today().year

    # Convert 0 ("now") to current year
    start_year = current_year if drink_from == 0 else drink_from
    end_year = current_year if drink_to == 0 else drink_to

    # If only drink_to is set, assume it's ready now
    if start_year is None:
        start_year = current_year

    # If only drink_from is set, no end date
    if end_year is None:
        if current_year < start_year:
            years_to_wait = start_year - current_year
            return mark_safe(
                f'<span class="drink-window drink-window--young">'
                f'<i class="fa-solid fa-hourglass-start drink-window__icon"></i>'
                f"{years_to_wait}+ years"
                f"</span>"
            )
        else:
            return mark_safe(
                '<span class="drink-window drink-window--ready">'
                '<i class="fa-solid fa-check-circle drink-window__icon"></i>'
                "Ready"
                "</span>"
            )

    if current_year < start_year:
        # Too young
        years_to_wait = start_year - current_year
        return mark_safe(
            f'<span class="drink-window drink-window--young">'
            f'<i class="fa-solid fa-hourglass-start drink-window__icon"></i>'
            f"{years_to_wait}+ years"
            f"</span>"
        )
    elif current_year <= end_year:
        # Ready to drink
        return mark_safe(
            '<span class="drink-window drink-window--ready">'
            '<i class="fa-solid fa-check-circle drink-window__icon"></i>'
            "Ready"
            "</span>"
        )
    else:
        # Past prime
        return mark_safe(
            '<span class="drink-window drink-window--prime">'
            '<i class="fa-solid fa-exclamation-triangle drink-window__icon"></i>'
            "Past prime"
            "</span>"
        )
