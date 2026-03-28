from rest_framework import serializers

from wine_cellar.apps.storage.models import BottleMoveHistory, Storage, StorageItem
from wine_cellar.apps.whisky.models import (
    Whisky,
    WhiskyBottleMoveHistory,
    WhiskyStorageItem,
)
from wine_cellar.apps.wine.models import Wine

# --- Storage ---


class StorageListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Storage
        exclude = ["user", "household"]


class StorageDetailSerializer(serializers.ModelSerializer):
    total_slots = serializers.IntegerField(read_only=True)
    used_slots = serializers.IntegerField(read_only=True)

    class Meta:
        model = Storage
        exclude = ["user", "household"]


# --- Wine StorageItem ---


class StorageItemReadSerializer(serializers.ModelSerializer):
    storage_name = serializers.CharField(source="storage.name", read_only=True)
    wine_name = serializers.CharField(source="wine.name", read_only=True)

    class Meta:
        model = StorageItem
        exclude = ["user", "household", "deleted"]


class StorageItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = StorageItem
        exclude = ["user", "household", "deleted"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and hasattr(request, "api_key"):
            hh = request.api_key.household
            self.fields["storage"].queryset = Storage.objects.filter(household=hh)
            self.fields["wine"].queryset = Wine.objects.filter(
                household=hh, deleted=False
            )


# --- Whisky StorageItem ---


class WhiskyStorageItemReadSerializer(serializers.ModelSerializer):
    storage_name = serializers.CharField(source="storage.name", read_only=True)
    whisky_name = serializers.CharField(source="whisky.name", read_only=True)

    class Meta:
        model = WhiskyStorageItem
        exclude = ["user", "household", "deleted"]


class WhiskyStorageItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhiskyStorageItem
        exclude = ["user", "household", "deleted"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and hasattr(request, "api_key"):
            hh = request.api_key.household
            self.fields["storage"].queryset = Storage.objects.filter(household=hh)
            self.fields["whisky"].queryset = Whisky.objects.filter(
                household=hh, deleted=False
            )


# --- Move histories ---


class BottleMoveHistorySerializer(serializers.ModelSerializer):
    from_storage_name = serializers.CharField(
        source="from_storage.name", read_only=True, default=None
    )
    to_storage_name = serializers.CharField(
        source="to_storage.name", read_only=True, default=None
    )

    class Meta:
        model = BottleMoveHistory
        exclude = ["user"]


class WhiskyBottleMoveHistorySerializer(serializers.ModelSerializer):
    from_storage_name = serializers.CharField(
        source="from_storage.name", read_only=True, default=None
    )
    to_storage_name = serializers.CharField(
        source="to_storage.name", read_only=True, default=None
    )

    class Meta:
        model = WhiskyBottleMoveHistory
        exclude = ["user"]
