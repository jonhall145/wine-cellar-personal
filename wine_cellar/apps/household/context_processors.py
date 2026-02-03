"""Context processor for household data in templates."""

from wine_cellar.apps.household.models import HouseholdMembership


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

    return {
        "active_household": active_household,
        "user_households": households,
        "has_multiple_households": has_multiple_households,
    }
