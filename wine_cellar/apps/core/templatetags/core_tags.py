from django import template
from django.utils.safestring import mark_safe

register = template.Library()


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
