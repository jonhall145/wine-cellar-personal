from wine_cellar.apps.api.mixins import (
    GlobalReferenceViewSet,
    HouseholdScopedModelViewSet,
    HouseholdScopedReadOnlyViewSet,
)
from wine_cellar.apps.api.serializers.whisky import (
    BottlerSerializer,
    DistillerySerializer,
    WhiskyAttributeSerializer,
    WhiskyBottleNoteSerializer,
    WhiskyCollectionReadSerializer,
    WhiskyCollectionWriteSerializer,
    WhiskyDrinkRecordSerializer,
    WhiskyPriceHistorySerializer,
    WhiskyReadSerializer,
    WhiskyRegionSerializer,
    WhiskySourceSerializer,
    WhiskyWishlistSerializer,
    WhiskyWriteSerializer,
)
from wine_cellar.apps.whisky.models import (
    Bottler,
    Collection,
    Distillery,
    Whisky,
    WhiskyAttribute,
    WhiskyBottleNote,
    WhiskyDrinkRecord,
    WhiskyPriceHistory,
    WhiskyRegion,
    WhiskySource,
    WhiskyWishlist,
)


class WhiskyViewSet(HouseholdScopedModelViewSet):
    queryset = Whisky.objects.all()

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return WhiskyReadSerializer
        return WhiskyWriteSerializer

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(deleted=False)
            .with_related()
            .with_stock_count()
            .prefetch_related("barcodes", "cask_history")
        )


class WhiskyAttributeViewSet(HouseholdScopedModelViewSet):
    serializer_class = WhiskyAttributeSerializer
    queryset = WhiskyAttribute.objects.all()


class WhiskySourceViewSet(HouseholdScopedModelViewSet):
    serializer_class = WhiskySourceSerializer
    queryset = WhiskySource.objects.all()


class WhiskyCollectionViewSet(HouseholdScopedModelViewSet):
    queryset = Collection.objects.all()

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return WhiskyCollectionReadSerializer
        return WhiskyCollectionWriteSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action in ("list", "retrieve"):
            qs = qs.prefetch_related(
                "whiskies__distillery",
                "whiskies__region",
                "whiskies__bottler",
                "whiskies__source",
                "whiskies__attributes",
                "whiskies__images",
                "whiskies__barcodes",
                "whiskies__cask_history",
            )
        return qs


class WhiskyDrinkRecordViewSet(HouseholdScopedModelViewSet):
    serializer_class = WhiskyDrinkRecordSerializer
    queryset = WhiskyDrinkRecord.objects.all()


class WhiskyWishlistViewSet(HouseholdScopedModelViewSet):
    serializer_class = WhiskyWishlistSerializer
    queryset = WhiskyWishlist.objects.all()


class WhiskyBottleNoteViewSet(HouseholdScopedModelViewSet):
    serializer_class = WhiskyBottleNoteSerializer
    queryset = WhiskyBottleNote.objects.all()


class WhiskyPriceHistoryViewSet(HouseholdScopedReadOnlyViewSet):
    serializer_class = WhiskyPriceHistorySerializer
    queryset = WhiskyPriceHistory.objects.all()


class WhiskyRegionViewSet(GlobalReferenceViewSet):
    serializer_class = WhiskyRegionSerializer
    queryset = WhiskyRegion.objects.all()


class DistilleryViewSet(GlobalReferenceViewSet):
    serializer_class = DistillerySerializer
    queryset = Distillery.objects.all()


class BottlerViewSet(GlobalReferenceViewSet):
    serializer_class = BottlerSerializer
    queryset = Bottler.objects.all()
