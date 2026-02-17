import os

from django.conf import settings


def app_context(request):
    """Expose app type and branding to all templates."""
    app_type = getattr(settings, "CELLAR_APP_TYPE", "wine")
    
    # Get explicit URLs from environment, or fall back to SITE_URL
    wine_url = os.environ.get("WINE_SITE_URL", "")
    whisky_url = os.environ.get("WHISKY_SITE_URL", "")
    
    # If explicit URLs aren't set, fall back to SITE_URL
    site_url = os.environ.get("SITE_URL", "")
    
    if app_type == "whisky":
        # For whisky app, switch to wine URL
        switch_url = wine_url if wine_url else site_url.replace("whisky.", "wine.") if site_url else ""
        return {
            "CELLAR_APP_TYPE": "whisky",
            "APP_NAME": "Whisky Cabinet",
            "APP_ITEM_NAME": "whisky",
            "APP_ITEM_NAME_PLURAL": "whiskies",
            "SWITCH_APP_URL": switch_url,
            "SWITCH_APP_NAME": "Wine Cellar",
            "SWITCH_APP_ICON": "fa-wine-bottle",
        }
    
    # For wine app, switch to whisky URL
    switch_url = whisky_url if whisky_url else site_url.replace("wine.", "whisky.") if site_url else ""
    return {
        "CELLAR_APP_TYPE": "wine",
        "APP_NAME": "Wine Cellar",
        "APP_ITEM_NAME": "wine",
        "APP_ITEM_NAME_PLURAL": "wines",
        "SWITCH_APP_URL": switch_url,
        "SWITCH_APP_NAME": "Whisky Cabinet",
        "SWITCH_APP_ICON": "fa-whiskey-glass",
    }
