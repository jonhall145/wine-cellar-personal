from django.conf import settings


def app_context(request):
    """Expose app type and branding to all templates."""
    app_type = getattr(settings, "CELLAR_APP_TYPE", "wine")
    if app_type == "whisky":
        return {
            "CELLAR_APP_TYPE": "whisky",
            "APP_NAME": "Whisky Cabinet",
            "APP_ITEM_NAME": "whisky",
            "APP_ITEM_NAME_PLURAL": "whiskies",
        }
    return {
        "CELLAR_APP_TYPE": "wine",
        "APP_NAME": "Wine Cellar",
        "APP_ITEM_NAME": "wine",
        "APP_ITEM_NAME_PLURAL": "wines",
    }
