from rest_framework import serializers

from wine_cellar.apps.whisky.models import (
    Bottler,
    CaskHistory,
    Collection,
    Distillery,
    Whisky,
    WhiskyAttribute,
    WhiskyBarcode,
    WhiskyBottleNote,
    WhiskyDrinkRecord,
    WhiskyImage,
    WhiskyPriceHistory,
    WhiskyRegion,
    WhiskySource,
    WhiskyWishlist,
)

# --- Reference serializers ---


class WhiskyRegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhiskyRegion
        fields = [
            "id",
            "name",
            "slug",
            "country",
            "latitude",
            "longitude",
            "description",
            "order",
        ]


class DistillerySerializer(serializers.ModelSerializer):
    region = WhiskyRegionSerializer(read_only=True)
    country_name = serializers.CharField(read_only=True)

    class Meta:
        model = Distillery
        fields = [
            "id",
            "name",
            "region",
            "country",
            "country_name",
            "latitude",
            "longitude",
            "status",
            "founded_year",
            "closed_year",
            "owner",
            "description",
            "is_user_created",
        ]


class BottlerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bottler
        fields = [
            "id",
            "name",
            "short_name",
            "country",
            "website",
            "description",
            "is_user_created",
        ]


class WhiskyAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhiskyAttribute
        fields = ["id", "name", "created", "modified"]
        read_only_fields = ["created", "modified"]


class WhiskySourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhiskySource
        fields = ["id", "name", "url", "created", "modified"]
        read_only_fields = ["created", "modified"]


class CaskHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CaskHistory
        fields = [
            "id",
            "order",
            "cask_type",
            "wood_type",
            "previous_contents",
            "duration_years",
            "is_finish",
            "cask_number",
            "description",
        ]


class WhiskyImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhiskyImage
        fields = ["id", "image", "thumbnail", "image_type", "is_primary", "created"]
        read_only_fields = ["id", "created"]


class WhiskyBarcodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhiskyBarcode
        fields = ["id", "barcode", "created"]
        read_only_fields = ["id", "created"]


# --- Whisky serializers ---


class WhiskyReadSerializer(serializers.ModelSerializer):
    distillery = DistillerySerializer(read_only=True)
    region = WhiskyRegionSerializer(read_only=True)
    bottler = BottlerSerializer(read_only=True)
    source = WhiskySourceSerializer(read_only=True)
    attributes = WhiskyAttributeSerializer(many=True, read_only=True)
    cask_history = CaskHistorySerializer(many=True, read_only=True)
    images = WhiskyImageSerializer(many=True, read_only=True)
    barcodes = WhiskyBarcodeSerializer(many=True, read_only=True)
    stock_count = serializers.IntegerField(read_only=True, default=0)
    country_name = serializers.CharField(read_only=True)
    whisky_type_display = serializers.CharField(
        source="get_whisky_type_display", read_only=True
    )
    is_official_bottling = serializers.BooleanField(read_only=True)
    is_nas = serializers.BooleanField(read_only=True)

    class Meta:
        model = Whisky
        exclude = ["user", "household", "deleted"]


class WhiskyWriteSerializer(serializers.ModelSerializer):
    attributes = serializers.PrimaryKeyRelatedField(
        many=True, queryset=WhiskyAttribute.objects.all(), required=False
    )

    class Meta:
        model = Whisky
        exclude = ["user", "household", "deleted"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and hasattr(request, "api_key"):
            hh = request.api_key.household
            self.fields["attributes"].child_relation.queryset = (
                WhiskyAttribute.objects.filter(household=hh)
            )
            if "source" in self.fields:
                self.fields["source"].queryset = WhiskySource.objects.filter(
                    household=hh
                )

    def create(self, validated_data):
        attributes = validated_data.pop("attributes", [])
        whisky = super().create(validated_data)
        whisky.attributes.set(attributes)
        return whisky

    def update(self, instance, validated_data):
        attributes = validated_data.pop("attributes", None)
        instance = super().update(instance, validated_data)
        if attributes is not None:
            instance.attributes.set(attributes)
        return instance


class WhiskySummarySerializer(serializers.ModelSerializer):
    """Slim serializer for embedding whiskies in collections."""

    whisky_type_display = serializers.CharField(
        source="get_whisky_type_display", read_only=True
    )

    class Meta:
        model = Whisky
        fields = [
            "id",
            "name",
            "whisky_type",
            "whisky_type_display",
            "country",
            "age_statement",
        ]


# --- Collection ---


class WhiskyCollectionReadSerializer(serializers.ModelSerializer):
    whiskies = WhiskySummarySerializer(many=True, read_only=True)

    class Meta:
        model = Collection
        exclude = ["user", "household"]


class WhiskyCollectionWriteSerializer(serializers.ModelSerializer):
    whiskies = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Whisky.objects.all(), required=False
    )

    class Meta:
        model = Collection
        exclude = ["user", "household"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and hasattr(request, "api_key"):
            hh = request.api_key.household
            self.fields["whiskies"].child_relation.queryset = Whisky.objects.filter(
                household=hh, deleted=False
            )

    def create(self, validated_data):
        whiskies = validated_data.pop("whiskies", [])
        collection = super().create(validated_data)
        collection.whiskies.set(whiskies)
        return collection

    def update(self, instance, validated_data):
        whiskies = validated_data.pop("whiskies", None)
        instance = super().update(instance, validated_data)
        if whiskies is not None:
            instance.whiskies.set(whiskies)
        return instance


# --- DrinkRecord ---


class WhiskyDrinkRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhiskyDrinkRecord
        exclude = ["user", "household"]


# --- Wishlist ---


class WhiskyWishlistSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhiskyWishlist
        exclude = ["user", "household"]


# --- BottleNote ---


class WhiskyBottleNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhiskyBottleNote
        exclude = ["user", "household"]


# --- PriceHistory ---


class WhiskyPriceHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = WhiskyPriceHistory
        exclude = ["user", "household"]
