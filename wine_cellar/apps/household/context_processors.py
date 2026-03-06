"""Context processor for household data in templates."""

from django.conf import settings

from wine_cellar.apps.household.models import HouseholdMembership


def _get_bottle_count(household):
    """Get total bottles in stock for the active household."""
    app_type = getattr(settings, "CELLAR_APP_TYPE", "wine")
    if app_type == "whisky":
        from wine_cellar.apps.whisky.models import WhiskyStorageItem

        return WhiskyStorageItem.objects.filter(
            household=household, deleted=False
        ).count()
    else:
        from wine_cellar.apps.storage.models import StorageItem

        return StorageItem.objects.filter(household=household, deleted=False).count()


def household_context(request):
    """Add household data to template context."""
    if not request.user.is_authenticated:
        return {}

    # Get user's active household
    active_household = None
    if hasattr(request.user, "user_settings") and request.user.user_settings:
        active_household = request.user.user_settings.active_household

    # Get all households user belongs to
    memberships = HouseholdMembership.objects.filter(user=request.user).select_related(
        "household"
    )

    households = [m.household for m in memberships]
    has_multiple_households = len(households) > 1

    # Bottle count for nav bar
    bottle_count = _get_bottle_count(active_household) if active_household else 0

    return {
        "active_household": active_household,
        "user_households": households,
        "has_multiple_households": has_multiple_households,
        "nav_bottle_count": bottle_count,
    }
