"""
URL configuration for wine_cellar project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
"""

import logging
import os
from email.utils import formatdate, parsedate_to_datetime

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponseNotModified
from django.urls import include, path, re_path
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_http_methods
from django.views.i18n import JavaScriptCatalog
from django.views.static import serve

from wine_cellar.apps.storage.views import (
    StorageCreateView,
    StorageDeleteView,
    StorageDetailView,
    StorageListView,
    StorageUpdateView,
    move_bottle,
    storage_grid_data,
    storage_move_down,
    storage_move_up,
)
from wine_cellar.apps.user.views import UserSettingsView

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".svg"}
# Health check disk space threshold in GB
CRITICAL_DISK_SPACE_GB = 0.1


@login_not_required
def serve_media(request, path):
    """Serve media files with cache headers and 304 support."""
    fullpath = os.path.join(settings.MEDIA_ROOT, path)

    # Handle If-Modified-Since for conditional requests
    if os.path.isfile(fullpath):
        mtime = os.path.getmtime(fullpath)

        ims = request.META.get("HTTP_IF_MODIFIED_SINCE")
        if ims:
            try:
                ims_dt = parsedate_to_datetime(ims)
                if mtime <= ims_dt.timestamp():
                    return HttpResponseNotModified()
            except (ValueError, TypeError):
                pass

    response = serve(request, path, document_root=settings.MEDIA_ROOT)

    # Only add cache headers to successful responses
    if response.status_code == 200:
        ext = os.path.splitext(path)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            response["Cache-Control"] = "public, max-age=86400"
        else:
            response["Cache-Control"] = "public, max-age=3600"

        if os.path.isfile(fullpath):
            mtime = os.path.getmtime(fullpath)
            response["Last-Modified"] = formatdate(mtime, usegmt=True)

    return response


@login_not_required
@require_http_methods(["GET", "HEAD"])
@cache_page(60)  # Cache for 60 seconds to reduce DB/disk I/O from health check polling
def health_check(request):
    """Health check endpoint for container orchestration and monitoring.

    Returns minimal status to avoid information disclosure on this public
    endpoint. Performs DB and disk checks internally but only returns
    HTTP 200 (healthy) or 503 (unhealthy).
    """
    import shutil

    from django.db import connections
    from django.http import JsonResponse

    status_code = 200

    # Check database connectivity
    try:
        for conn in connections.all():
            conn.ensure_connection()
    except Exception:
        status_code = 503

    # Check disk space
    try:
        media_root = getattr(settings, "MEDIA_ROOT", "/tmp")
        disk_usage = shutil.disk_usage(media_root)
        free_gb = disk_usage.free / (1024**3)
        if free_gb < CRITICAL_DISK_SPACE_GB:
            status_code = 503
    except Exception:
        # Disk check failure shouldn't fail health check, but log it
        logger.exception("Disk check failed in health_check endpoint")

    # Return minimal response - rely primarily on HTTP status code
    response_data = {"status": "ok" if status_code == 200 else "unhealthy"}
    return JsonResponse(response_data, status=status_code)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("household/", include("wine_cellar.apps.household.urls")),
    path(
        "api/v1/", include("wine_cellar.apps.hardware.urls", namespace="hardware-api")
    ),
    path(
        "hardware/",
        include(
            ("wine_cellar.apps.hardware.web_urls", "hardware"), namespace="hardware"
        ),
    ),
    path("user/settings/", UserSettingsView.as_view(), name="user-settings"),
    # Storage (shared across wine/whisky)
    path("storages/", StorageListView.as_view(), name="storage-list"),
    path("storage/<int:pk>/", StorageDetailView.as_view(), name="storage-detail"),
    path("storage/add/", StorageCreateView.as_view(), name="storage-add"),
    path(
        "storage/delete/<int:pk>/", StorageDeleteView.as_view(), name="storage-delete"
    ),
    path("storage/edit/<int:pk>/", StorageUpdateView.as_view(), name="storage-edit"),
    path("storage/move-up/<int:pk>/", storage_move_up, name="storage-move-up"),
    path("storage/move-down/<int:pk>/", storage_move_down, name="storage-move-down"),
    path("api/storage/grid-data/", storage_grid_data, name="storage-grid-data"),
    path("api/storage/move-bottle/", move_bottle, name="storage-move-bottle"),
    # Shared utilities
    path("health/", health_check, name="health_check"),
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
]

# Include app-specific URLs
if settings.CELLAR_APP_TYPE == "whisky":
    urlpatterns += [path("", include("wine_cellar.apps.whisky.urls"))]
else:
    urlpatterns += [path("", include("wine_cellar.apps.wine.urls"))]

# Serve media files (in production, consider using nginx instead)
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve_media),
]
