from django.urls import path

from wine_cellar.apps.whisky import views

urlpatterns = [
    # Homepage
    path("", views.HomePageView.as_view(), name="homepage"),
    # Random bottle picker
    path("random/", views.RandomBottleView.as_view(), name="random-bottle"),
    # Whisky CRUD
    path("whiskies/", views.WhiskyListView.as_view(), name="whisky-list"),
    path("whisky/add/", views.WhiskyCreateView.as_view(), name="whisky-add"),
    path("whisky/<int:pk>/", views.WhiskyDetailView.as_view(), name="whisky-detail"),
    path(
        "whisky/<int:pk>/collections/add/",
        views.add_whisky_to_collection,
        name="whisky-collection-add",
    ),
    path(
        "whisky/<int:pk>/collections/<int:collection_pk>/remove/",
        views.remove_whisky_from_collection,
        name="whisky-collection-remove",
    ),
    path("whisky/<int:pk>/qr/", views.QRCodeView.as_view(), name="whisky-qr"),
    path("whisky/edit/<int:pk>/", views.WhiskyUpdateView.as_view(), name="whisky-edit"),
    path(
        "whisky/delete/<int:pk>/",
        views.WhiskyDeleteView.as_view(),
        name="whisky-delete",
    ),
    # Scanning
    path("whisky/scan/", views.WhiskyScanView.as_view(), name="whisky-scan"),
    path(
        "whisky/scan/<str:code>/",
        views.WhiskyScannedView.as_view(),
        name="whisky-scanned",
    ),
    path("label-scan/", views.LabelScanView.as_view(), name="label-scan"),
    # AJAX endpoints
    path(
        "whisky/check-duplicate/",
        views.whisky_check_duplicate_ajax,
        name="whisky-check-duplicate",
    ),
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
        "whisky/merge/<int:pk>/into/<int:primary_pk>/",
        views.WhiskyMergeConfirmView.as_view(),
        name="whisky-merge-confirm",
    ),
    # Storage/Bottles
    path("bottles/", views.StorageItemListView.as_view(), name="bottle-list"),
    path("stock/add/<int:pk>/", views.StorageItemAddView.as_view(), name="stock-add"),
    path(
        "stock/delete/<int:pk>/",
        views.StorageItemDeleteView.as_view(),
        name="stock-delete",
    ),
    path(
        "stock/give/<int:pk>/",
        views.StorageItemMarkGivenView.as_view(),
        name="stock-give",
    ),
    path(
        "bottle/edit/<int:pk>/",
        views.StorageItemUpdateView.as_view(),
        name="bottle-edit",
    ),
    path(
        "storage/history/",
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
    path("journey/", views.JourneyTimelineView.as_view(), name="journey-timeline"),
    path(
        "drink-history/edit/<int:pk>/",
        views.DrinkRecordEditView.as_view(),
        name="drink-record-edit",
    ),
    path(
        "drink-history/delete/<int:pk>/",
        views.DrinkRecordDeleteView.as_view(),
        name="drink-record-delete",
    ),
    # Wishlist
    path("wishlist/", views.WishlistListView.as_view(), name="wishlist-list"),
    path("wishlist/add/", views.WishlistCreateView.as_view(), name="wishlist-add"),
    path(
        "wishlist/delete/<int:pk>/",
        views.WishlistDeleteView.as_view(),
        name="wishlist-delete",
    ),
    path(
        "wishlist/purchased/<int:pk>/",
        views.WishlistPurchasedView.as_view(),
        name="wishlist-purchased",
    ),
    # Stats & reports
    path("cellar-value/", views.CellarValueView.as_view(), name="cellar-value"),
    path("stats/", views.ConsumptionStatsView.as_view(), name="consumption-stats"),
    path("dashboard/", views.StatsDashboardView.as_view(), name="stats-dashboard"),
    path(
        "alerts/",
        views.DrinkingWindowAlertsView.as_view(),
        name="drinking-alerts",
    ),
    # Reorder reminders
    path("reorder/", views.ReorderRemindersView.as_view(), name="reorder-reminders"),
    path(
        "reorder/add/<int:pk>/",
        views.ReorderReminderCreateView.as_view(),
        name="reorder-reminder-add",
    ),
    path(
        "reorder/delete/<int:pk>/",
        views.ReorderReminderDeleteView.as_view(),
        name="reorder-reminder-delete",
    ),
    # Bottle notes
    path(
        "bottle/<int:pk>/note/",
        views.BottleNoteCreateView.as_view(),
        name="bottle-note-add",
    ),
    # Bottle history
    path(
        "bottle/<int:pk>/history/",
        views.WhiskyBottleHistoryView.as_view(),
        name="bottle-history",
    ),
    path(
        "stock/<int:pk>/quick-log/",
        views.WhiskyBottleQuickLogView.as_view(),
        name="bottle-quick-log",
    ),
]

# Keep legacy whisky URLs working for saved links and bookmarks.
urlpatterns += [
    path("whisky/<int:pk>/edit/", views.WhiskyUpdateView.as_view()),
    path("whisky/<int:pk>/delete/", views.WhiskyDeleteView.as_view()),
    path("whisky/scanned/<str:code>/", views.WhiskyScannedView.as_view()),
    path(
        "whisky/<int:pk>/merge/<int:primary_pk>/",
        views.WhiskyMergeConfirmView.as_view(),
    ),
    path("whisky/<int:pk>/stock/add/", views.StorageItemAddView.as_view()),
    path("stock/<int:pk>/delete/", views.StorageItemDeleteView.as_view()),
    path("stock/<int:pk>/give/", views.StorageItemMarkGivenView.as_view()),
    path("stock/<int:pk>/edit/", views.StorageItemUpdateView.as_view()),
    path("drink-record/<int:pk>/edit/", views.DrinkRecordEditView.as_view()),
    path("drink-record/<int:pk>/delete/", views.DrinkRecordDeleteView.as_view()),
    path("wishlist/<int:pk>/delete/", views.WishlistDeleteView.as_view()),
    path("wishlist/<int:pk>/purchased/", views.WishlistPurchasedView.as_view()),
    path("whisky/<int:pk>/reorder/add/", views.ReorderReminderCreateView.as_view()),
    path("reorder/<int:pk>/delete/", views.ReorderReminderDeleteView.as_view()),
    path("stock/<int:pk>/note/add/", views.BottleNoteCreateView.as_view()),
    path("stock/<int:pk>/history/", views.WhiskyBottleHistoryView.as_view()),
]
