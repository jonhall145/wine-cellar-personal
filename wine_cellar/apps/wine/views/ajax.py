import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.dateformat import format as date_format
from django_ratelimit.decorators import ratelimit

from wine_cellar.apps.core.views import (
    check_beverage_duplicate_ajax,
    crop_image_ajax,
    set_primary_image_ajax,
)
from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.wine.models import Wine, WineBarcode, WineImage

logger = logging.getLogger(__name__)


@login_required
def set_primary_image(request, pk):
    """Set a WineImage as the primary image for its wine."""
    return set_primary_image_ajax(request, pk, WineImage)


@login_required
def delete_wine_barcode(request, pk):
    """Delete a WineBarcode by pk (POST only)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    household = get_active_household(request.user)
    barcode = get_object_or_404(WineBarcode, pk=pk, household=household)
    barcode.delete()
    return JsonResponse({"success": True})


@login_required
def crop_wine_image(request, pk):
    """Apply manual crop to a WineImage and create a new thumbnail."""
    return crop_image_ajax(request, pk, WineImage)


@login_required
def export_wines_csv_view(request):
    """Export all wines as CSV."""
    from wine_cellar.apps.wine.export import export_wines_csv

    household = get_active_household(request.user)
    return export_wines_csv(household)


@login_required
def export_wines_json_view(request):
    """Export all wines as JSON."""
    from wine_cellar.apps.wine.export import export_wines_json

    household = get_active_household(request.user)
    return export_wines_json(household)


@ratelimit(key="user", rate="60/m", method="GET", block=True)
@login_required
def wine_check_duplicate_ajax(request):
    """AJAX endpoint to check for wines with similar names."""
    return check_beverage_duplicate_ajax(
        request,
        beverage_model=Wine,
        detail_url_name="wine-detail",
    )


@ratelimit(key="user", rate="60/m", method="GET", block=True)
@login_required
def wine_ai_summary_status(request, pk):
    """Return the generated AI summary once it is available."""
    household = get_active_household(request.user)
    wine = get_object_or_404(
        Wine.objects.filter(deleted=False),
        pk=pk,
        household=household,
    )
    if not wine.ai_summary:
        return JsonResponse({"status": "pending"})

    return JsonResponse(
        {
            "status": "ready",
            "summary": wine.ai_summary,
            "sources": wine.ai_summary_sources,
            "generated_at": (
                date_format(wine.ai_summary_generated_at, "SHORT_DATETIME_FORMAT")
                if wine.ai_summary_generated_at
                else ""
            ),
        }
    )
