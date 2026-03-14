from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from wine_cellar.apps.core.templatetags.core_tags import (
    _badge_impl,
    _rating_stars_impl,
)
from wine_cellar.apps.whisky.utils import classify_cask_type

register = template.Library()


WHISKY_TYPE_CLASSES = {
    "SM": "single-malt",
    "BM": "blended-malt",
    "BL": "blended",
    "SG": "single-grain",
}

WHISKY_TYPE_LABELS = {
    "SM": "Single Malt",
    "BM": "Blended Malt",
    "BL": "Blended",
    "SG": "Single Grain",
}

PEATED_LEVEL_CLASSES = {
    "UP": "unpeated",
    "PE": "peated",
}

PEATED_LEVEL_LABELS = {
    "UP": "Unpeated",
    "PE": "Peated",
}

FILL_LEVEL_ICONS = {
    "UN": "fa-solid fa-battery-full",
    "OP": "fa-solid fa-battery-half",
    "DR": "fa-solid fa-battery-empty",
}

FILL_LEVEL_LABELS = {
    "UN": "Unopened",
    "OP": "Opened",
    "DR": "Dreg",
}

FILL_LEVEL_CLASSES = {
    "UN": "unopened",
    "OP": "opened",
    "DR": "dreg",
}


@register.filter
def cask_border_css(whisky):
    """Return CSS class suffix for card border based on cask type and strength."""
    category = classify_cask_type(getattr(whisky, "cask_type", ""))
    is_cs = getattr(whisky, "cask_strength", False)
    suffix = f"cask-{category}"
    if is_cs:
        suffix += "-cs"
    return suffix


rating_stars = register.simple_tag(_rating_stars_impl, name="rating_stars")


@register.simple_tag
def whisky_type_badge(whisky_type: str) -> str:
    """Render a colored badge for the whisky type."""
    return _badge_impl(
        whisky_type, WHISKY_TYPE_CLASSES, WHISKY_TYPE_LABELS, "whisky-type-badge"
    )


@register.simple_tag
def peated_badge(peated_level: str) -> str:
    """Render a badge for the peated level."""
    return _badge_impl(
        peated_level, PEATED_LEVEL_CLASSES, PEATED_LEVEL_LABELS, "peated-badge"
    )


@register.simple_tag
def fill_level_display(fill_level: str) -> str:
    """Render fill level indicator with icon and text."""
    if not fill_level:
        return ""

    icon_class = FILL_LEVEL_ICONS.get(fill_level, "fa-solid fa-battery-full")
    label = FILL_LEVEL_LABELS.get(fill_level, fill_level)
    css_class = FILL_LEVEL_CLASSES.get(fill_level, "")

    if not css_class:
        return mark_safe(
            f'<span class="fill-level">'
            f'<i class="{escape(icon_class)} fill-level__icon"></i>'
            f"{escape(label)}"
            f"</span>"
        )

    return mark_safe(
        f'<span class="fill-level fill-level--{escape(css_class)}">'
        f'<i class="{escape(icon_class)} fill-level__icon"></i>'
        f"{escape(label)}"
        f"</span>"
    )
