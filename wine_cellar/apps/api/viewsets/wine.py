from wine_cellar.apps.api.mixins import (
    GlobalReferenceViewSet,
    HouseholdScopedModelViewSet,
    HouseholdScopedReadOnlyViewSet,
)
from wine_cellar.apps.api.serializers.wine import (
    AppellationSerializer,
    AttributeSerializer,
    BottleNoteSerializer,
    DrinkRecordSerializer,
    FoodPairingSerializer,
    GrapeSerializer,
    PriceHistorySerializer,
    SizeSerializer,
    SourceSerializer,
    VineyardSerializer,
    WineCollectionReadSerializer,
    WineCollectionWriteSerializer,
    WineReadSerializer,
    WineWriteSerializer,
    WishlistSerializer,
)
from wine_cellar.apps.wine.models import (
    Appellation,
    Attribute,
    BottleNote,
    Collection,
    DrinkRecord,
    FoodPairing,
    Grape,
    PriceHistory,
    Size,
    Source,
    Vineyard,
    Wine,
    Wishlist,
)


class WineViewSet(HouseholdScopedModelViewSet):
    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return WineReadSerializer
        return WineWriteSerializer

    queryset = Wine.objects.all()
    filterset_fields = ["wine_type", "country", "vintage", "rating"]
    search_fields = ["name", "comment"]
    ordering_fields = ["name", "vintage", "rating", "created"]

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(deleted=False)
            .with_related()
            .with_stock_count()
            .prefetch_related("barcodes")
        )


class GrapeViewSet(HouseholdScopedModelViewSet):
    serializer_class = GrapeSerializer
    queryset = Grape.objects.all()


class VineyardViewSet(HouseholdScopedModelViewSet):
    serializer_class = VineyardSerializer
    queryset = Vineyard.objects.all()


class FoodPairingViewSet(HouseholdScopedModelViewSet):
    serializer_class = FoodPairingSerializer
    queryset = FoodPairing.objects.all()


class AttributeViewSet(HouseholdScopedModelViewSet):
    serializer_class = AttributeSerializer
    queryset = Attribute.objects.all()


class SourceViewSet(HouseholdScopedModelViewSet):
    serializer_class = SourceSerializer
    queryset = Source.objects.all()


class SizeViewSet(HouseholdScopedModelViewSet):
    serializer_class = SizeSerializer
    queryset = Size.objects.all()


class WineCollectionViewSet(HouseholdScopedModelViewSet):
    queryset = Collection.objects.all()

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return WineCollectionReadSerializer
        return WineCollectionWriteSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action in ("list", "retrieve"):
            qs = qs.prefetch_related("wines")
        return qs


class DrinkRecordViewSet(HouseholdScopedModelViewSet):
    serializer_class = DrinkRecordSerializer
    queryset = DrinkRecord.objects.all()


class WishlistViewSet(HouseholdScopedModelViewSet):
    serializer_class = WishlistSerializer
    queryset = Wishlist.objects.all()


class BottleNoteViewSet(HouseholdScopedModelViewSet):
    serializer_class = BottleNoteSerializer
    queryset = BottleNote.objects.all()


class PriceHistoryViewSet(HouseholdScopedReadOnlyViewSet):
    serializer_class = PriceHistorySerializer
    queryset = PriceHistory.objects.all()


class AppellationViewSet(GlobalReferenceViewSet):
    serializer_class = AppellationSerializer
    queryset = Appellation.objects.all()
