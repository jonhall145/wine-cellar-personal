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
def rating_stars(rating, max_rating=10):
    """Render star rating display (converts 10-point scale to 5 stars)."""
    if rating is None:
        return mark_safe('<span class="rating-stars rating-stars--empty">—</span>')

    # Convert 10-point rating to 5-star scale
    stars = (float(rating) / max_rating) * 5
    full_stars = int(stars)
    has_half = (stars - full_stars) >= 0.5
    empty_stars = 5 - full_stars - (1 if has_half else 0)

    html = '<span class="rating-stars">'

    # Full stars
    for _i in range(full_stars):
        html += (
            '<i class="fa-solid fa-star rating-stars__star '
            'rating-stars__star--filled"></i>'
        )

    # Half star
    if has_half:
        html += (
            '<i class="fa-solid fa-star-half-stroke rating-stars__star '
            'rating-stars__star--filled"></i>'
        )

    # Empty stars
    for _j in range(empty_stars):
        html += '<i class="fa-regular fa-star rating-stars__star"></i>'

    html += '</span>'

    return mark_safe(html)


@register.simple_tag
def drink_window_indicator(vintage, drink_by):
    """Show whether a wine is ready to drink, too young, or past its prime."""
    if not vintage or not drink_by:
        return ""

    current_year = date.today().year

    try:
        drink_by_year = int(drink_by)
    except (ValueError, TypeError):
        return ""

    # Estimate optimal drinking window (typically 2-3 years before drink_by)
    optimal_start = drink_by_year - 3

    if current_year < optimal_start:
        # Too young
        years_to_wait = optimal_start - current_year
        return mark_safe(
            f'<span class="drink-window drink-window--young">'
            f'<i class="fa-solid fa-hourglass-start drink-window__icon"></i>'
            f'{years_to_wait}+ years'
            f'</span>'
        )
    elif current_year <= drink_by_year:
        # Ready to drink
        return mark_safe(
            '<span class="drink-window drink-window--ready">'
            '<i class="fa-solid fa-check-circle drink-window__icon"></i>'
            'Ready'
            '</span>'
        )
    else:
        # Past prime
        return mark_safe(
            '<span class="drink-window drink-window--prime">'
            '<i class="fa-solid fa-exclamation-triangle drink-window__icon"></i>'
            'Past prime'
            '</span>'
        )
