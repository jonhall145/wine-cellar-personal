from django.urls import path

from wine_cellar.apps.storage.views import (
    BottleHistoryView,
    BottleQuickLogView,
    StorageItemAddView,
    StorageItemDeleteView,
    StorageItemHistoryView,
    StorageItemListView,
    StorageItemMarkGivenView,
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
    JourneyTimelineView,
    LabelScanView,
    QRCodeView,
    RandomBottleView,
    ReorderReminderCreateView,
    ReorderReminderDeleteView,
    ReorderRemindersView,
    StatsDashboardView,
    WineCreateView,
    WineDeleteView,
    WineDetailView,
    WineImagesView,
    WineImportView,
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
    add_price_history,
    add_wine_to_collection,
    bulk_action_view,
    crop_wine_image,
    delete_wine_barcode,
    export_wines_csv_view,
    export_wines_json_view,
    extract_wine_vision_ajax,
    remove_wine_from_collection,
    scan_barcode_ajax,
    set_primary_image,
    wine_check_duplicate_ajax,
)

urlpatterns = [
    # Stock / bottle management
    path("stock/add/<int:pk>/", StorageItemAddView.as_view(), name="stock-add"),
    path(
        "stock/delete/<int:pk>/", StorageItemDeleteView.as_view(), name="stock-delete"
    ),
    path("stock/give/<int:pk>/", StorageItemMarkGivenView.as_view(), name="stock-give"),
    path("bottles/", StorageItemListView.as_view(), name="bottle-list"),
    path("bottle/edit/<int:pk>/", StorageItemUpdateView.as_view(), name="bottle-edit"),
    path("storage/history/", StorageItemHistoryView.as_view(), name="stock-history"),
    # Wine CRUD
    path("wine/add/", WineCreateView.as_view(), name="wine-add"),
    path("wine/add/<str:code>/", WineCreateView.as_view(), name="wine-add"),
    path(
        "wine/check-duplicate/",
        wine_check_duplicate_ajax,
        name="wine-check-duplicate",
    ),
    path("wine/extract-vision/", extract_wine_vision_ajax, name="wine-extract-vision"),
    path("wine/<int:pk>/", WineDetailView.as_view(), name="wine-detail"),
    path(
        "wine/<int:pk>/price-history/add/",
        add_price_history,
        name="wine-price-history-add",
    ),
    path(
        "wine/<int:pk>/collections/add/",
        add_wine_to_collection,
        name="wine-collection-add",
    ),
    path(
        "wine/<int:pk>/collections/<int:collection_pk>/remove/",
        remove_wine_from_collection,
        name="wine-collection-remove",
    ),
    path("wine/<int:pk>/qr/", QRCodeView.as_view(), name="wine-qr"),
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
    path("wines/import/", WineImportView.as_view(), name="wine-import"),
    path("wines/export/csv/", export_wines_csv_view, name="wine-export-csv"),
    path("wines/export/json/", export_wines_json_view, name="wine-export-json"),
    path("wines/bulk/", bulk_action_view, name="wine-bulk-action"),
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
    path("journey/", JourneyTimelineView.as_view(), name="journey-timeline"),
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
    path("dashboard/", StatsDashboardView.as_view(), name="stats-dashboard"),
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
    # Random bottle picker
    path("random/", RandomBottleView.as_view(), name="random-bottle"),
    # Bottle history
    path(
        "bottle/<int:pk>/history/",
        BottleHistoryView.as_view(),
        name="bottle-history",
    ),
    path(
        "bottle/<int:pk>/quick-log/",
        BottleQuickLogView.as_view(),
        name="bottle-quick-log",
    ),
    # Homepage
    path("", HomePageView.as_view(), name="homepage"),
]
