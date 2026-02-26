from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from wine_cellar.apps.core.templatetags.core_tags import _rating_stars_impl
from wine_cellar.apps.whisky.utils import classify_cask_type

register = template.Library()


WHISKY_TYPE_CLASSES = {
    "SM": "single-malt",
    "BM": "blended-malt",
    "BL": "blended",
    "SG": "single-grain",
}

WHISKY_TYPE_LABELS = {
    "SM": _("Single Malt"),
    "BM": _("Blended Malt"),
    "BL": _("Blended"),
    "SG": _("Single Grain"),
}

PEATED_LEVEL_CLASSES = {
    "UP": "unpeated",
    "PE": "peated",
}

PEATED_LEVEL_LABELS = {
    "UP": _("Unpeated"),
    "PE": _("Peated"),
}

FILL_LEVEL_ICONS = {
    "UN": "fa-solid fa-battery-full",
    "OP": "fa-solid fa-battery-half",
    "DR": "fa-solid fa-battery-empty",
}

FILL_LEVEL_LABELS = {
    "UN": _("Unopened"),
    "OP": _("Opened"),
    "DR": _("Dreg"),
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
    if not whisky_type:
        return ""

    css_class = WHISKY_TYPE_CLASSES.get(whisky_type, "")
    label = WHISKY_TYPE_LABELS.get(whisky_type, whisky_type)

    if not css_class:
        return mark_safe(f'<span class="whisky-type-badge">{escape(label)}</span>')

    return mark_safe(
        f'<span class="whisky-type-badge whisky-type-badge--{escape(css_class)}">'
        f"{escape(label)}</span>"
    )


@register.simple_tag
def peated_badge(peated_level: str) -> str:
    """Render a badge for the peated level."""
    if not peated_level:
        return ""

    css_class = PEATED_LEVEL_CLASSES.get(peated_level, "")
    label = PEATED_LEVEL_LABELS.get(peated_level, peated_level)

    if not css_class:
        return mark_safe(f'<span class="peated-badge">{escape(label)}</span>')

    return mark_safe(
        f'<span class="peated-badge peated-badge--{escape(css_class)}">'
        f"{escape(label)}</span>"
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
