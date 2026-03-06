from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.db import connections
from django.http import JsonResponse


@login_not_required
def health_check(request):
    """Health check endpoint for container orchestration and monitoring."""
    import shutil

    health = {
        "status": "ok",
        "database": "ok",
        "disk": "ok",
    }
    status_code = 200

    try:
        for conn in connections.all():
            conn.ensure_connection()
    except Exception:
        health["database"] = "unhealthy"
        health["status"] = "unhealthy"
        status_code = 503

    try:
        media_root = getattr(settings, "MEDIA_ROOT", "/tmp")
        disk_usage = shutil.disk_usage(media_root)
        free_gb = disk_usage.free / (1024**3)
        health["disk_free_gb"] = round(free_gb, 2)
        if free_gb < 1:
            health["disk"] = "low"
            if free_gb < 0.1:
                health["disk"] = "critical"
                health["status"] = "unhealthy"
                status_code = 503
    except Exception:
        health["disk"] = "unknown"

    return JsonResponse(health, status=status_code)
