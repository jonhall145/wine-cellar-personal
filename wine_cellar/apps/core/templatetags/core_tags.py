from django import template
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def bev_url(context, action, *args):
    """Resolve app-specific URLs dynamically.

    Usage: {% bev_url 'detail' object.pk %}
    Resolves to 'wine-detail' or 'whisky-detail' based on CELLAR_APP_TYPE.
    """
    app_type = context.get("CELLAR_APP_TYPE", "wine")
    url_name = f"{app_type}-{action}"
    return reverse(url_name, args=args)


@register.filter
def getbeverage(record, fk_name):
    """Get beverage FK from a record dynamically.

    Usage: {{ record|getbeverage:beverage_fk_name }}
    Works with both model instances (getattr) and dicts (key access).
    """
    if isinstance(record, dict):
        return record.get(fk_name)
    return getattr(record, fk_name, None)


def _rating_stars_impl(rating, max_rating=3):
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


rating_stars = register.simple_tag(_rating_stars_impl, name="rating_stars")


def _badge_impl(code, classes_map, labels_map, css_prefix):
    """Render a colored badge span.

    Args:
        code: The type code (e.g. "RE", "SM", "PE")
        classes_map: Dict mapping code to CSS class suffix
        labels_map: Dict mapping code to display label
        css_prefix: CSS class prefix (e.g. "wine-type-badge", "whisky-type-badge")
    """
    if not code:
        return ""

    css_class = classes_map.get(code, "")
    label = labels_map.get(code, code)

    if not css_class:
        return mark_safe(f'<span class="{css_prefix}">{escape(label)}</span>')

    return mark_safe(
        f'<span class="{css_prefix} {css_prefix}--{escape(css_class)}">'
        f"{escape(label)}</span>"
    )
