from rest_framework.routers import DefaultRouter

from wine_cellar.apps.api.viewsets.storage import (
    BottleMoveHistoryViewSet,
    StorageItemViewSet,
    StorageViewSet,
    WhiskyBottleMoveHistoryViewSet,
    WhiskyStorageItemViewSet,
)
from wine_cellar.apps.api.viewsets.whisky import (
    BottlerViewSet,
    DistilleryViewSet,
    WhiskyAttributeViewSet,
    WhiskyBottleNoteViewSet,
    WhiskyCollectionViewSet,
    WhiskyDrinkRecordViewSet,
    WhiskyPriceHistoryViewSet,
    WhiskyRegionViewSet,
    WhiskySourceViewSet,
    WhiskyViewSet,
    WhiskyWishlistViewSet,
)
from wine_cellar.apps.api.viewsets.wine import (
    AppellationViewSet,
    AttributeViewSet,
    BottleNoteViewSet,
    DrinkRecordViewSet,
    FoodPairingViewSet,
    GrapeViewSet,
    PriceHistoryViewSet,
    SizeViewSet,
    SourceViewSet,
    VineyardViewSet,
    WineCollectionViewSet,
    WineViewSet,
    WishlistViewSet,
)

router = DefaultRouter()

# Wine resources
router.register("wines", WineViewSet, basename="wine")
router.register("grapes", GrapeViewSet, basename="grape")
router.register("vineyards", VineyardViewSet, basename="vineyard")
router.register("food-pairings", FoodPairingViewSet, basename="food-pairing")
router.register("wine-attributes", AttributeViewSet, basename="wine-attribute")
router.register("wine-sources", SourceViewSet, basename="wine-source")
router.register("sizes", SizeViewSet, basename="size")
router.register("wine-collections", WineCollectionViewSet, basename="wine-collection")
router.register("drink-records", DrinkRecordViewSet, basename="drink-record")
router.register("wine-wishlist", WishlistViewSet, basename="wine-wishlist")
router.register("wine-bottle-notes", BottleNoteViewSet, basename="wine-bottle-note")
router.register(
    "wine-price-history", PriceHistoryViewSet, basename="wine-price-history"
)
router.register("appellations", AppellationViewSet, basename="appellation")

# Whisky resources
router.register("whiskies", WhiskyViewSet, basename="whisky")
router.register(
    "whisky-attributes", WhiskyAttributeViewSet, basename="whisky-attribute"
)
router.register("whisky-sources", WhiskySourceViewSet, basename="whisky-source")
router.register(
    "whisky-collections", WhiskyCollectionViewSet, basename="whisky-collection"
)
router.register(
    "whisky-drink-records", WhiskyDrinkRecordViewSet, basename="whisky-drink-record"
)
router.register("whisky-wishlist", WhiskyWishlistViewSet, basename="whisky-wishlist")
router.register(
    "whisky-bottle-notes", WhiskyBottleNoteViewSet, basename="whisky-bottle-note"
)
router.register(
    "whisky-price-history", WhiskyPriceHistoryViewSet, basename="whisky-price-history"
)
router.register("whisky-regions", WhiskyRegionViewSet, basename="whisky-region")
router.register("distilleries", DistilleryViewSet, basename="distillery")
router.register("bottlers", BottlerViewSet, basename="bottler")

# Storage resources
router.register("storages", StorageViewSet, basename="api-storage")
router.register("wine-bottles", StorageItemViewSet, basename="wine-bottle")
router.register("whisky-bottles", WhiskyStorageItemViewSet, basename="whisky-bottle")
router.register(
    "wine-move-history", BottleMoveHistoryViewSet, basename="wine-move-history"
)
router.register(
    "whisky-move-history",
    WhiskyBottleMoveHistoryViewSet,
    basename="whisky-move-history",
)

urlpatterns = router.urls
