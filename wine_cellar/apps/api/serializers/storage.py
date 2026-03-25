from rest_framework import serializers

from wine_cellar.apps.storage.models import BottleMoveHistory, Storage, StorageItem
from wine_cellar.apps.whisky.models import WhiskyBottleMoveHistory, WhiskyStorageItem

# --- Storage ---


class StorageSerializer(serializers.ModelSerializer):
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
        fields = "__all__"


class WhiskyBottleMoveHistorySerializer(serializers.ModelSerializer):
    from_storage_name = serializers.CharField(
        source="from_storage.name", read_only=True, default=None
    )
    to_storage_name = serializers.CharField(
        source="to_storage.name", read_only=True, default=None
    )

    class Meta:
        model = WhiskyBottleMoveHistory
        fields = "__all__"
