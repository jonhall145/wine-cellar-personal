"""URL configuration for hardware API and web endpoints."""

from django.urls import path

from . import views

app_name = "hardware"

# Web UI routes
web_urlpatterns = [
    path("reviews/", views.PositionReviewView.as_view(), name="position-reviews"),
    path("devices/", views.DeviceSettingsView.as_view(), name="device-settings"),
    path("rack-config/", views.RackConfigView.as_view(), name="rack-config"),
]

# API routes (under /api/v1/)
api_urlpatterns = [
    # Health check
    path("health/", views.api_health_check, name="health"),

    # Device management
    path("devices/register/", views.register_device, name="register-device"),

    # Position change endpoints
    path("position-change/", views.report_position_change, name="position-change"),
    path("pending-reviews/", views.get_pending_reviews, name="pending-reviews"),
    path(
        "reviews/<int:review_id>/approve/",
        views.approve_review,
        name="approve-review",
    ),
    path("reviews/<int:review_id>/reject/", views.reject_review, name="reject-review"),

    # Rack snapshot endpoints
    path("rack-snapshot/", views.upload_rack_snapshot, name="rack-snapshot"),

    # Sync endpoints
    path("sync/", views.sync_operations, name="sync"),

    # Wine endpoints
    path(
        "wines/barcode/<str:barcode>/",
        views.get_wine_by_barcode,
        name="wine-by-barcode",
    ),
    path("wines/<int:wine_id>/", views.get_wine, name="wine-detail"),
    path("wines/from-labels/", views.create_wine_from_labels, name="wine-from-labels"),

    # Storage endpoints
    path(
        "storage/racks/<int:rack_id>/positions/",
        views.get_rack_positions,
        name="rack-positions",
    ),
    path(
        "storage/racks/<int:rack_id>/positions/<int:row>/<int:col>/",
        views.get_position,
        name="position-detail",
    ),
    path("storage/add/", views.add_wine_to_position, name="storage-add"),
    path("storage/remove/", views.remove_wine_from_position, name="storage-remove"),
]

# Default urlpatterns is the API endpoints for backwards compatibility
urlpatterns = api_urlpatterns
