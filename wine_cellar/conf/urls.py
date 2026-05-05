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
from django.core.exceptions import SuspiciousFileOperation
from django.http import Http404, HttpResponseNotModified
from django.urls import include, path, re_path
from django.utils._os import safe_join
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView
from django.views.static import serve

from wine_cellar.apps.core.api import (
    api_cellar_sync,
    api_push_subscribe,
    api_push_unsubscribe,
    api_vapid_public_key,
    api_version,
)
from wine_cellar.apps.core.pwa import manifest_json, service_worker_js
from wine_cellar.apps.user.views import (
    NotificationCentreView,
    NotificationDismissView,
    NotificationMarkReadView,
    UserBackupExportView,
    UserBackupImportView,
    UserSettingsView,
)

logger = logging.getLogger("wine_cellar.health_check")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".svg"}
# Health check disk space threshold in GB
CRITICAL_DISK_SPACE_GB = 0.1


@login_not_required
def serve_media(request, path):
    """Serve media files with cache headers and 304 support."""
    try:
        fullpath = safe_join(settings.MEDIA_ROOT, path)
    except SuspiciousFileOperation:
        raise Http404

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
@cache_page(10)  # Cache for 10 seconds to reduce load while staying responsive
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
        # If disk check fails (e.g., path inaccessible), log but don't fail
        # Only actual low disk space (checked successfully) should fail health
        logger.exception("Disk check failed in health_check endpoint")

    # Return minimal response - rely primarily on HTTP status code
    response_data = {"status": "ok" if status_code == 200 else "unhealthy"}
    return JsonResponse(response_data, status=status_code)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("household/", include("wine_cellar.apps.household.urls")),
    path("user/settings/", UserSettingsView.as_view(), name="user-settings"),
    path("notifications/", NotificationCentreView.as_view(), name="notifications"),
    path(
        "notifications/read/",
        NotificationMarkReadView.as_view(),
        name="notification-mark-read",
    ),
    path(
        "notifications/dismiss/",
        NotificationDismissView.as_view(),
        name="notification-dismiss",
    ),
    path(
        "user/settings/backup/export/",
        UserBackupExportView.as_view(),
        name="user-backup-export",
    ),
    path(
        "user/settings/backup/import/",
        UserBackupImportView.as_view(),
        name="user-backup-import",
    ),
    # Storage (shared across wine/whisky)
    path("", include("wine_cellar.apps.storage.urls")),
    # Shared utilities
    path("health/", health_check, name="health_check"),
    # PWA
    path("manifest.json", manifest_json, name="pwa-manifest"),
    path("sw.js", service_worker_js, name="pwa-service-worker"),
    path(
        "offline/",
        login_not_required(
            cache_page(3600)(TemplateView.as_view(template_name="offline.html"))
        ),
        name="pwa-offline",
    ),
    # API
    path("api/cellar/sync/", api_cellar_sync, name="api-cellar-sync"),
    path("api/push/subscribe/", api_push_subscribe, name="api-push-subscribe"),
    path(
        "api/push/unsubscribe/",
        api_push_unsubscribe,
        name="api-push-unsubscribe",
    ),
    path(
        "api/push/vapid-key/",
        api_vapid_public_key,
        name="api-vapid-public-key",
    ),
    path("api/version/", api_version, name="api-version"),
    # REST API
    path("rest/", include("wine_cellar.apps.api.urls")),
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
