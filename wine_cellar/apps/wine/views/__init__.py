"""Wine views package — re-exports all views for backward compatibility."""

from wine_cellar.apps.wine.views.ajax import (  # noqa: F401
    crop_wine_image,
    delete_wine_barcode,
    export_wines_csv_view,
    export_wines_json_view,
    set_primary_image,
    wine_check_duplicate_ajax,
)
from wine_cellar.apps.wine.views.bulk import bulk_action_view  # noqa: F401
from wine_cellar.apps.wine.views.cellar import (  # noqa: F401
    CellarValueView,
    ConsumptionStatsView,
    StatsDashboardView,
)
from wine_cellar.apps.wine.views.drink import (  # noqa: F401
    BottleNoteCreateView,
    DrinkingWindowAlertsView,
    DrinkRecordCreateView,
    DrinkRecordDeleteView,
    DrinkRecordEditView,
    DrinkRecordListView,
    JourneyTimelineView,
)
from wine_cellar.apps.wine.views.health import health_check  # noqa: F401
from wine_cellar.apps.wine.views.home import (  # noqa: F401
    HomePageView,
    QRCodeView,
    RandomBottleView,
)
from wine_cellar.apps.wine.views.map import WineMapView  # noqa: F401
from wine_cellar.apps.wine.views.reminders import (  # noqa: F401
    ReorderReminderCreateView,
    ReorderReminderDeleteView,
    ReorderRemindersView,
)
from wine_cellar.apps.wine.views.scan import (  # noqa: F401
    LabelScanResultView,
    LabelScanView,
    WineScannedView,
    WineScanView,
    extract_wine_vision_ajax,
    scan_barcode_ajax,
)
from wine_cellar.apps.wine.views.wine_crud import (  # noqa: F401
    FINAL_FORM_STEP,
    WineCreateView,
    WineDeleteView,
    WineDetailView,
    WineImagesView,
    WineListView,
    WineMergeConfirmView,
    WineUpdateView,
    add_price_history,
    add_wine_to_collection,
    remove_wine_from_collection,
)
from wine_cellar.apps.wine.views.wishlist import (  # noqa: F401
    WishlistCreateView,
    WishlistDeleteView,
    WishlistListView,
    WishlistPurchasedView,
)
