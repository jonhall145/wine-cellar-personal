from django.urls import path

from wine_cellar.apps.whisky import views

urlpatterns = [
    # Homepage
    path("", views.HomePageView.as_view(), name="homepage"),
    # Whisky CRUD
    path("whiskies/", views.WhiskyListView.as_view(), name="whisky-list"),
    path("whisky/add/", views.WhiskyCreateView.as_view(), name="whisky-add"),
    path("whisky/<int:pk>/", views.WhiskyDetailView.as_view(), name="whisky-detail"),
    path("whisky/<int:pk>/edit/", views.WhiskyUpdateView.as_view(), name="whisky-edit"),
    path(
        "whisky/<int:pk>/delete/",
        views.WhiskyDeleteView.as_view(),
        name="whisky-delete",
    ),
    # Scanning
    path("whisky/scan/", views.WhiskyScanView.as_view(), name="whisky-scan"),
    path(
        "whisky/scanned/<str:code>/",
        views.WhiskyScannedView.as_view(),
        name="whisky-scanned",
    ),
    path("whisky/label-scan/", views.LabelScanView.as_view(), name="label-scan"),
    # AJAX endpoints
    path(
        "whisky/extract-vision/",
        views.extract_whisky_vision_ajax,
        name="whisky-extract-vision",
    ),
    path(
        "whisky/scan-barcode/",
        views.scan_barcode_ajax,
        name="whisky-scan-barcode",
    ),
    # Map
    path("whiskies/map/", views.WhiskyMapView.as_view(), name="whisky-map"),
    # Images
    path(
        "whisky/<int:pk>/images/",
        views.WhiskyImagesView.as_view(),
        name="whisky-images",
    ),
    path(
        "whisky/image/<int:pk>/set-primary/",
        views.set_primary_image,
        name="set-primary-image",
    ),
    path(
        "whisky/image/<int:pk>/crop/",
        views.crop_whisky_image,
        name="crop-whisky-image",
    ),
    # Merge
    path(
        "whisky/<int:pk>/merge/<int:primary_pk>/",
        views.WhiskyMergeConfirmView.as_view(),
        name="whisky-merge-confirm",
    ),
    # Storage/Bottles
    path("bottles/", views.StorageItemListView.as_view(), name="bottle-list"),
    path(
        "whisky/<int:pk>/stock/add/",
        views.StorageItemAddView.as_view(),
        name="stock-add",
    ),
    path(
        "stock/<int:pk>/delete/",
        views.StorageItemDeleteView.as_view(),
        name="stock-delete",
    ),
    path(
        "stock/<int:pk>/edit/",
        views.StorageItemUpdateView.as_view(),
        name="bottle-edit",
    ),
    path(
        "stock/<int:pk>/history/",
        views.StorageItemHistoryView.as_view(),
        name="stock-history",
    ),
    # Drink records
    path(
        "whisky/<int:pk>/drink/",
        views.DrinkRecordCreateView.as_view(),
        name="drink-record-add",
    ),
    path("drink-history/", views.DrinkRecordListView.as_view(), name="drink-history"),
    path(
        "drink-record/<int:pk>/edit/",
        views.DrinkRecordEditView.as_view(),
        name="drink-record-edit",
    ),
    path(
        "drink-record/<int:pk>/delete/",
        views.DrinkRecordDeleteView.as_view(),
        name="drink-record-delete",
    ),
    # Wishlist
    path("wishlist/", views.WishlistListView.as_view(), name="wishlist-list"),
    path("wishlist/add/", views.WishlistCreateView.as_view(), name="wishlist-add"),
    path(
        "wishlist/<int:pk>/delete/",
        views.WishlistDeleteView.as_view(),
        name="wishlist-delete",
    ),
    path(
        "wishlist/<int:pk>/purchased/",
        views.WishlistPurchasedView.as_view(),
        name="wishlist-purchased",
    ),
    # Stats & reports
    path("cellar-value/", views.CellarValueView.as_view(), name="cellar-value"),
    path("stats/", views.ConsumptionStatsView.as_view(), name="consumption-stats"),
    path(
        "alerts/",
        views.DrinkingWindowAlertsView.as_view(),
        name="drinking-alerts",
    ),
    # Reorder reminders
    path("reorder/", views.ReorderRemindersView.as_view(), name="reorder-reminders"),
    path(
        "whisky/<int:pk>/reorder/add/",
        views.ReorderReminderCreateView.as_view(),
        name="reorder-reminder-add",
    ),
    path(
        "reorder/<int:pk>/delete/",
        views.ReorderReminderDeleteView.as_view(),
        name="reorder-reminder-delete",
    ),
    # Sale alerts
    path("sale-alerts/", views.SaleAlertsView.as_view(), name="sale-alerts"),
    path(
        "whisky/<int:pk>/sale-alert/add/",
        views.SaleAlertCreateView.as_view(),
        name="sale-alert-add",
    ),
    path(
        "sale-alert/<int:pk>/delete/",
        views.SaleAlertDeleteView.as_view(),
        name="sale-alert-delete",
    ),
    path(
        "sale-alert/<int:pk>/toggle/",
        views.SaleAlertToggleView.as_view(),
        name="sale-alert-toggle",
    ),
    # Bottle notes
    path(
        "stock/<int:pk>/note/add/",
        views.BottleNoteCreateView.as_view(),
        name="bottle-note-add",
    ),
]
