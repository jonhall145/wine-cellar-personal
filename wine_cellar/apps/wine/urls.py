from django.urls import path

from wine_cellar.apps.storage.views import (
    StorageItemAddView,
    StorageItemDeleteView,
    StorageItemHistoryView,
    StorageItemListView,
    StorageItemUpdateView,
)
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
    WineCreateView,
    WineDeleteView,
    WineDetailView,
    WineImagesView,
    WineListView,
    WineMapView,
    WineMergeConfirmView,
    WineScannedView,
    WineScanView,
    WineUpdateView,
    WishlistCreateView,
    WishlistDeleteView,
    WishlistListView,
    WishlistPurchasedView,
    crop_wine_image,
    delete_wine_barcode,
    extract_wine_vision_ajax,
    scan_barcode_ajax,
    set_primary_image,
)

urlpatterns = [
    # Stock / bottle management
    path("stock/add/<int:pk>/", StorageItemAddView.as_view(), name="stock-add"),
    path(
        "stock/delete/<int:pk>/", StorageItemDeleteView.as_view(), name="stock-delete"
    ),
    path("bottles/", StorageItemListView.as_view(), name="bottle-list"),
    path("bottle/edit/<int:pk>/", StorageItemUpdateView.as_view(), name="bottle-edit"),
    path("storage/history/", StorageItemHistoryView.as_view(), name="stock-history"),
    # Wine CRUD
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
        "wine/merge/<int:pk>/into/<int:primary_pk>/",
        WineMergeConfirmView.as_view(),
        name="wine-merge-confirm",
    ),
    path(
        "wine/<int:pk>/drink/", DrinkRecordCreateView.as_view(), name="drink-record-add"
    ),
    path("wines/", WineListView.as_view(), name="wine-list"),
    path("wine/scan/", WineScanView.as_view(), name="wine-scan"),
    path("wine/scan/<str:code>/", WineScannedView.as_view(), name="wine-scan"),
    path("wine/scan-barcode/", scan_barcode_ajax, name="wine-scan-barcode"),
    path("wines/map/", WineMapView.as_view(), name="wine-map"),
    # Drink history
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
    # Wishlist
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
    # Cellar value & stats
    path("cellar-value/", CellarValueView.as_view(), name="cellar-value"),
    path(
        "bottle/<int:pk>/note/", BottleNoteCreateView.as_view(), name="bottle-note-add"
    ),
    path("alerts/", DrinkingWindowAlertsView.as_view(), name="drinking-alerts"),
    path("stats/", ConsumptionStatsView.as_view(), name="consumption-stats"),
    # Reorder reminders
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
    # Barcodes
    path(
        "wine/barcode/<int:pk>/delete/",
        delete_wine_barcode,
        name="wine-barcode-delete",
    ),
    # Label scanning
    path("label-scan/", LabelScanView.as_view(), name="label-scan"),
    # Homepage
    path("", HomePageView.as_view(), name="homepage"),
]
