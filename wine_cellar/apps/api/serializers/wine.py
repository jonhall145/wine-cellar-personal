from rest_framework import serializers

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
    WineBarcode,
    WineImage,
    Wishlist,
)

# --- Simple reference serializers ---


class GrapeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grape
        fields = ["id", "name", "created", "modified"]
        read_only_fields = ["created", "modified"]


class VineyardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vineyard
        fields = ["id", "name", "website", "region", "country", "created", "modified"]
        read_only_fields = ["created", "modified"]


class FoodPairingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodPairing
        fields = ["id", "name", "created", "modified"]
        read_only_fields = ["created", "modified"]


class AttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attribute
        fields = ["id", "name", "created", "modified"]
        read_only_fields = ["created", "modified"]


class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = ["id", "name", "url", "price_selector", "created", "modified"]
        read_only_fields = ["created", "modified"]


class SizeSerializer(serializers.ModelSerializer):
    display = serializers.CharField(source="__str__", read_only=True)

    class Meta:
        model = Size
        fields = ["id", "name", "display", "created", "modified"]
        read_only_fields = ["created", "modified"]


class AppellationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appellation
        fields = [
            "id",
            "name",
            "country",
            "latitude",
            "longitude",
            "parent_region",
        ]


class WineImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = WineImage
        fields = ["id", "image", "thumbnail", "image_type", "is_primary"]
        read_only_fields = ["id"]


class WineBarcodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = WineBarcode
        fields = ["id", "barcode", "created"]
        read_only_fields = ["id", "created"]


# --- Wine serializers ---


class WineReadSerializer(serializers.ModelSerializer):
    grapes = GrapeSerializer(many=True, read_only=True)
    attributes = AttributeSerializer(many=True, read_only=True)
    food_pairings = FoodPairingSerializer(many=True, read_only=True)
    vineyard = VineyardSerializer(many=True, read_only=True)
    source = SourceSerializer(many=True, read_only=True)
    appellation = AppellationSerializer(read_only=True)
    size = SizeSerializer(read_only=True)
    images = WineImageSerializer(source="wineimage_set", many=True, read_only=True)
    barcodes = WineBarcodeSerializer(many=True, read_only=True)
    stock_count = serializers.IntegerField(read_only=True, default=0)
    wine_type_display = serializers.CharField(source="get_type", read_only=True)
    country_name = serializers.CharField(read_only=True)

    class Meta:
        model = Wine
        exclude = ["user", "household", "deleted"]


class WineWriteSerializer(serializers.ModelSerializer):
    grapes = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Grape.objects.all(), required=False
    )
    attributes = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Attribute.objects.all(), required=False
    )
    food_pairings = serializers.PrimaryKeyRelatedField(
        many=True, queryset=FoodPairing.objects.all(), required=False
    )
    vineyard = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Vineyard.objects.all(), required=False
    )
    source = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Source.objects.all(), required=False
    )

    class Meta:
        model = Wine
        exclude = ["user", "household", "deleted"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and hasattr(request, "api_key"):
            hh = request.api_key.household
            self.fields["grapes"].child_relation.queryset = Grape.objects.filter(
                household=hh
            )
            self.fields["attributes"].child_relation.queryset = (
                Attribute.objects.filter(household=hh)
            )
            self.fields["food_pairings"].child_relation.queryset = (
                FoodPairing.objects.filter(household=hh)
            )
            self.fields["vineyard"].child_relation.queryset = Vineyard.objects.filter(
                household=hh
            )
            self.fields["source"].child_relation.queryset = Source.objects.filter(
                household=hh
            )
            if "size" in self.fields:
                self.fields["size"].queryset = Size.objects.filter(household=hh)

    def create(self, validated_data):
        m2m = {
            "grapes": validated_data.pop("grapes", []),
            "attributes": validated_data.pop("attributes", []),
            "food_pairings": validated_data.pop("food_pairings", []),
            "vineyard": validated_data.pop("vineyard", []),
            "source": validated_data.pop("source", []),
        }
        wine = super().create(validated_data)
        for field, values in m2m.items():
            getattr(wine, field).set(values)
        return wine

    def update(self, instance, validated_data):
        m2m = {}
        for field in ["grapes", "attributes", "food_pairings", "vineyard", "source"]:
            if field in validated_data:
                m2m[field] = validated_data.pop(field)
        instance = super().update(instance, validated_data)
        for field, values in m2m.items():
            getattr(instance, field).set(values)
        return instance


# --- Collection ---


class WineCollectionReadSerializer(serializers.ModelSerializer):
    wines = WineReadSerializer(many=True, read_only=True)

    class Meta:
        model = Collection
        exclude = ["user", "household"]


class WineCollectionWriteSerializer(serializers.ModelSerializer):
    wines = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Wine.objects.all(), required=False
    )

    class Meta:
        model = Collection
        exclude = ["user", "household"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and hasattr(request, "api_key"):
            hh = request.api_key.household
            self.fields["wines"].child_relation.queryset = Wine.objects.filter(
                household=hh, deleted=False
            )

    def create(self, validated_data):
        wines = validated_data.pop("wines", [])
        collection = super().create(validated_data)
        collection.wines.set(wines)
        return collection

    def update(self, instance, validated_data):
        wines = validated_data.pop("wines", None)
        instance = super().update(instance, validated_data)
        if wines is not None:
            instance.wines.set(wines)
        return instance


# --- DrinkRecord ---


class DrinkRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DrinkRecord
        exclude = ["user", "household"]


# --- Wishlist ---


class WishlistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wishlist
        exclude = ["user", "household"]


# --- BottleNote ---


class BottleNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = BottleNote
        exclude = ["user", "household"]


# --- PriceHistory ---


class PriceHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceHistory
        exclude = ["user", "household"]
