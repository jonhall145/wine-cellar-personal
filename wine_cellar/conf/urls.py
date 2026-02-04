"""
URL configuration for wine_cellar project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

import os
from email.utils import formatdate, parsedate_to_datetime

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponseNotModified
from django.urls import include, path, re_path
from django.views.i18n import JavaScriptCatalog
from django.views.static import serve

from wine_cellar.apps.storage.views import (
    StorageCreateView,
    StorageDeleteView,
    StorageDetailView,
    StorageItemAddView,
    StorageItemDeleteView,
    StorageItemHistoryView,
    StorageItemListView,
    StorageItemUpdateView,
    StorageListView,
    StorageUpdateView,
    move_bottle,
    storage_grid_data,
    storage_move_down,
    storage_move_up,
)
from wine_cellar.apps.user.views import UserSettingsView
from wine_cellar.apps.wine.views import (
    BottleNoteCreateView,
    CellarValueView,
    ConsumptionStatsView,
    DrinkingWindowAlertsView,
    DrinkRecordCreateView,
    DrinkRecordDeleteView,
    DrinkRecordEditView,
    DrinkRecordListView,
    HomePageView,
    LabelScanView,
    ReorderReminderCreateView,
    ReorderReminderDeleteView,
    ReorderRemindersView,
    SaleAlertCreateView,
    SaleAlertDeleteView,
    SaleAlertsView,
    SaleAlertToggleView,
    WineCreateView,
    WineDeleteView,
    WineDetailView,
    WineImagesView,
    WineListView,
    WineMapView,
    WineScannedView,
    WineScanView,
    WineUpdateView,
    WishlistCreateView,
    WishlistDeleteView,
    WishlistListView,
    WishlistPurchasedView,
    crop_wine_image,
    extract_wine_vision_ajax,
    health_check,
    scan_barcode_ajax,
    set_primary_image,
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".svg"}


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
    path("storages/", StorageListView.as_view(), name="storage-list"),
    path("storage/<int:pk>/", StorageDetailView.as_view(), name="storage-detail"),
    path("storage/add/", StorageCreateView.as_view(), name="storage-add"),
    path(
        "storage/delete/<int:pk>/", StorageDeleteView.as_view(), name="storage-delete"
    ),
    path("storage/edit/<int:pk>/", StorageUpdateView.as_view(), name="storage-edit"),
    path("storage/move-up/<int:pk>/", storage_move_up, name="storage-move-up"),
    path("storage/move-down/<int:pk>/", storage_move_down, name="storage-move-down"),
    path("storage/history/", StorageItemHistoryView.as_view(), name="storage-history"),
    path("api/storage/grid-data/", storage_grid_data, name="storage-grid-data"),
    path("api/storage/move-bottle/", move_bottle, name="storage-move-bottle"),
    path("stock/add/<int:pk>/", StorageItemAddView.as_view(), name="stock-add"),
    path(
        "stock/delete/<int:pk>/", StorageItemDeleteView.as_view(), name="stock-delete"
    ),
    path("bottles/", StorageItemListView.as_view(), name="bottle-list"),
    path("bottle/edit/<int:pk>/", StorageItemUpdateView.as_view(), name="bottle-edit"),
    path("wine/add/", WineCreateView.as_view(), name="wine-add"),
    path("wine/add/<str:code>/", WineCreateView.as_view(), name="wine-add"),
    path("wine/extract-vision/", extract_wine_vision_ajax, name="wine-extract-vision"),
    path("wine/<int:pk>/", WineDetailView.as_view(), name="wine-detail"),
    path("wine/<int:pk>/images/", WineImagesView.as_view(), name="wine-images"),
    path("wine/edit/<int:pk>/", WineUpdateView.as_view(), name="wine-edit"),
    path(
        "wine/image/<int:pk>/set-primary/", set_primary_image, name="set-primary-image"
    ),
    path("wine/image/<int:pk>/crop/", crop_wine_image, name="crop-wine-image"),
    path("wine/delete/<int:pk>/", WineDeleteView.as_view(), name="wine-delete"),
    path(
        "wine/<int:pk>/drink/", DrinkRecordCreateView.as_view(), name="drink-record-add"
    ),
    path("wines/", WineListView.as_view(), name="wine-list"),
    path("wine/scan/", WineScanView.as_view(), name="wine-scan"),
    path("wine/scan/<str:code>/", WineScannedView.as_view(), name="wine-scan"),
    path("wine/scan-barcode/", scan_barcode_ajax, name="wine-scan-barcode"),
    path("wines/map/", WineMapView.as_view(), name="wine-map"),
    path("drink-history/", DrinkRecordListView.as_view(), name="drink-history"),
    path(
        "drink-history/edit/<int:pk>/",
        DrinkRecordEditView.as_view(),
        name="drink-record-edit",
    ),
    path(
        "drink-history/delete/<int:pk>/",
        DrinkRecordDeleteView.as_view(),
        name="drink-record-delete",
    ),
    path("wishlist/", WishlistListView.as_view(), name="wishlist-list"),
    path("wishlist/add/", WishlistCreateView.as_view(), name="wishlist-add"),
    path(
        "wishlist/delete/<int:pk>/",
        WishlistDeleteView.as_view(),
        name="wishlist-delete",
    ),
    path(
        "wishlist/purchased/<int:pk>/",
        WishlistPurchasedView.as_view(),
        name="wishlist-purchased",
    ),
    path("cellar-value/", CellarValueView.as_view(), name="cellar-value"),
    path(
        "bottle/<int:pk>/note/", BottleNoteCreateView.as_view(), name="bottle-note-add"
    ),
    path("alerts/", DrinkingWindowAlertsView.as_view(), name="drinking-alerts"),
    path("stats/", ConsumptionStatsView.as_view(), name="consumption-stats"),
    path("reorder/", ReorderRemindersView.as_view(), name="reorder-reminders"),
    path(
        "reorder/add/<int:pk>/",
        ReorderReminderCreateView.as_view(),
        name="reorder-reminder-add",
    ),
    path(
        "reorder/delete/<int:pk>/",
        ReorderReminderDeleteView.as_view(),
        name="reorder-reminder-delete",
    ),
    path("sale-alerts/", SaleAlertsView.as_view(), name="sale-alerts"),
    path("sale-alerts/add/", SaleAlertCreateView.as_view(), name="sale-alert-add"),
    path(
        "sale-alerts/delete/<int:pk>/",
        SaleAlertDeleteView.as_view(),
        name="sale-alert-delete",
    ),
    path(
        "sale-alerts/toggle/<int:pk>/",
        SaleAlertToggleView.as_view(),
        name="sale-alert-toggle",
    ),
    path("label-scan/", LabelScanView.as_view(), name="label-scan"),
    path("storage/history/", StorageItemHistoryView.as_view(), name="stock-history"),
    path("health/", health_check, name="health_check"),
    path("", HomePageView.as_view(), name="homepage"),
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
]

# Serve media files (in production, consider using nginx instead)
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve_media),
]
