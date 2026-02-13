import os

from django.conf import settings


def app_context(request):
    """Expose app type and branding to all templates."""
    app_type = getattr(settings, "CELLAR_APP_TYPE", "wine")
    site_url = os.environ.get("SITE_URL", "")
    # Derive the other app's URL from the current site URL
    if app_type == "whisky":
        switch_url = site_url.replace("whisky.", "wine.") if site_url else ""
        return {
            "CELLAR_APP_TYPE": "whisky",
            "APP_NAME": "Whisky Cabinet",
            "APP_ITEM_NAME": "whisky",
            "APP_ITEM_NAME_PLURAL": "whiskies",
            "SWITCH_APP_URL": switch_url,
            "SWITCH_APP_NAME": "Wine Cellar",
            "SWITCH_APP_ICON": "fa-wine-bottle",
        }
    switch_url = (
        site_url.replace("wine.", "whisky.")
        .replace("test.", "whisky.")
        .replace("://jonandem.com", "://whisky.jonandem.com")
        if site_url
        else ""
    )
    return {
        "CELLAR_APP_TYPE": "wine",
        "APP_NAME": "Wine Cellar",
        "APP_ITEM_NAME": "wine",
        "APP_ITEM_NAME_PLURAL": "wines",
        "SWITCH_APP_URL": switch_url,
        "SWITCH_APP_NAME": "Whisky Cabinet",
        "SWITCH_APP_ICON": "fa-whiskey-glass",
    }
