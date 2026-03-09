import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from wine_cellar.apps.core.audit import log_delete
from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.wine.models import Wine

logger = logging.getLogger(__name__)


@require_POST
@login_required
def bulk_action_view(request):
    """Handle bulk actions on selected wines."""
    household = get_active_household(request.user)
    wine_ids = request.POST.getlist("wine_ids")
    action = request.POST.get("action")

    if not wine_ids:
        messages.warning(request, "No wines selected.")
        return redirect("wine-list")

    wines = Wine.objects.filter(household=household, pk__in=wine_ids, deleted=False)
    count = wines.count()

    if action == "delete":
        for wine in wines:
            log_delete(request.user, wine)
        wines.update(deleted=True)
        messages.success(request, f"Deleted {count} wine(s).")
    elif action == "update_drink_to":
        drink_to = request.POST.get("drink_to_year")
        if drink_to:
            try:
                drink_to = int(drink_to)
                wines.update(drink_to=drink_to)
                messages.success(
                    request, f"Updated drink-by year to {drink_to} for {count} wine(s)."
                )
            except (ValueError, TypeError):
                messages.error(request, "Invalid year value.")
        else:
            messages.warning(request, "No year specified.")
    else:
        messages.error(request, f"Unknown action: {action}")

    return redirect("wine-list")
