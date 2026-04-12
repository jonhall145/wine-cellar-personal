from django.db import transaction
from rest_framework import serializers as drf_serializers
from rest_framework.viewsets import ReadOnlyModelViewSet

from wine_cellar.apps.api.authentication import APIKeyAuthentication
from wine_cellar.apps.api.mixins import HouseholdScopedModelViewSet
from wine_cellar.apps.api.pagination import StandardPagination
from wine_cellar.apps.api.permissions import ScopeBasedPermission
from wine_cellar.apps.api.serializers.storage import (
    BottleMoveHistorySerializer,
    StorageDetailSerializer,
    StorageItemReadSerializer,
    StorageItemWriteSerializer,
    StorageListSerializer,
    WhiskyBottleMoveHistorySerializer,
    WhiskyStorageItemReadSerializer,
    WhiskyStorageItemWriteSerializer,
)
from wine_cellar.apps.storage.models import BottleMoveHistory, Storage, StorageItem
from wine_cellar.apps.whisky.models import WhiskyBottleMoveHistory, WhiskyStorageItem


def _validate_storage_position(storage, row, column, exclude_item=None):
    """Validate that a position is within bounds, active, and unoccupied."""
    is_grid = storage.rows > 0 and storage.columns > 0

    if not is_grid:
        # Non-grid storages don't use row/column positioning
        if row is not None or column is not None:
            raise drf_serializers.ValidationError(
                {"row": "This storage does not use grid positions."}
            )
        return

    # Grid storage: row and column are required
    if row is None or column is None:
        raise drf_serializers.ValidationError(
            {"row": "Row and column are required for grid storages."}
        )
    if row < 1 or row > storage.rows:
        raise drf_serializers.ValidationError(
            {"row": f"Row must be between 1 and {storage.rows}."}
        )
    if column < 1 or column > storage.columns:
        raise drf_serializers.ValidationError(
            {"column": f"Column must be between 1 and {storage.columns}."}
        )
    if not storage.is_cell_active(row, column):
        raise drf_serializers.ValidationError({"row": "Target cell is not active."})
    qs = storage._get_items().filter(row=row, column=column, deleted=False)
    if exclude_item:
        qs = qs.exclude(pk=exclude_item.pk)
    if qs.exists():
        raise drf_serializers.ValidationError(
            {"row": "Target position is already occupied."}
        )


class StorageViewSet(HouseholdScopedModelViewSet):
    queryset = Storage.objects.all()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return StorageDetailSerializer
        return StorageListSerializer


class StorageItemViewSet(HouseholdScopedModelViewSet):
    queryset = StorageItem.objects.all()

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return StorageItemReadSerializer
        return StorageItemWriteSerializer

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(deleted=False)
            .select_related("storage", "wine")
        )

    def perform_create(self, serializer):
        storage = serializer.validated_data.get("storage")
        row = serializer.validated_data.get("row")
        column = serializer.validated_data.get("column")
        if storage:
            _validate_storage_position(storage, row, column)
        super().perform_create(serializer)

    def perform_update(self, serializer):
        item = self.get_object()
        has_storage = "storage" in serializer.validated_data
        has_row = "row" in serializer.validated_data
        has_column = "column" in serializer.validated_data

        with transaction.atomic():
            item = (
                StorageItem.objects.select_for_update()
                .select_related("storage")
                .get(pk=item.pk)
            )
            old_storage = item.storage
            old_row = item.row
            old_column = item.column
            storage = (
                serializer.validated_data["storage"] if has_storage else old_storage
            )
            row = serializer.validated_data["row"] if has_row else old_row
            column = serializer.validated_data["column"] if has_column else old_column
            storage_ids = {old_storage.pk, storage.pk}
            list(
                Storage.objects.select_for_update()
                .filter(pk__in=storage_ids)
                .order_by("pk")
            )

            _validate_storage_position(storage, row, column, exclude_item=item)

            instance = serializer.save()
            moved = (
                old_storage.pk != instance.storage_id
                or old_row != instance.row
                or old_column != instance.column
            )
            if moved:
                BottleMoveHistory.objects.create(
                    storage_item=instance,
                    from_storage=old_storage,
                    from_row=old_row,
                    from_column=old_column,
                    to_storage=instance.storage,
                    to_row=instance.row,
                    to_column=instance.column,
                    user=self.request.api_key.user,
                )


class WhiskyStorageItemViewSet(HouseholdScopedModelViewSet):
    queryset = WhiskyStorageItem.objects.all()

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return WhiskyStorageItemReadSerializer
        return WhiskyStorageItemWriteSerializer

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(deleted=False)
            .select_related("storage", "whisky")
        )

    def perform_create(self, serializer):
        storage = serializer.validated_data.get("storage")
        row = serializer.validated_data.get("row")
        column = serializer.validated_data.get("column")
        if storage:
            _validate_storage_position(storage, row, column)
        super().perform_create(serializer)

    def perform_update(self, serializer):
        item = self.get_object()
        has_storage = "storage" in serializer.validated_data
        has_row = "row" in serializer.validated_data
        has_column = "column" in serializer.validated_data

        with transaction.atomic():
            item = (
                WhiskyStorageItem.objects.select_for_update()
                .select_related("storage")
                .get(pk=item.pk)
            )
            old_storage = item.storage
            old_row = item.row
            old_column = item.column
            storage = (
                serializer.validated_data["storage"] if has_storage else old_storage
            )
            row = serializer.validated_data["row"] if has_row else old_row
            column = serializer.validated_data["column"] if has_column else old_column
            storage_ids = {old_storage.pk, storage.pk}
            list(
                Storage.objects.select_for_update()
                .filter(pk__in=storage_ids)
                .order_by("pk")
            )

            _validate_storage_position(storage, row, column, exclude_item=item)

            instance = serializer.save()
            moved = (
                old_storage.pk != instance.storage_id
                or old_row != instance.row
                or old_column != instance.column
            )
            if moved:
                WhiskyBottleMoveHistory.objects.create(
                    storage_item=instance,
                    from_storage=old_storage,
                    from_row=old_row,
                    from_column=old_column,
                    to_storage=instance.storage,
                    to_row=instance.row,
                    to_column=instance.column,
                    user=self.request.api_key.user,
                )


class BottleMoveHistoryViewSet(ReadOnlyModelViewSet):
    """Read-only move history — filtered by storage_item's household."""

    authentication_classes = [APIKeyAuthentication]
    permission_classes = [ScopeBasedPermission]
    pagination_class = StandardPagination
    serializer_class = BottleMoveHistorySerializer
    queryset = BottleMoveHistory.objects.select_related(
        "from_storage", "to_storage"
    ).all()

    def get_queryset(self):
        household = self.request.api_key.household
        return super().get_queryset().filter(storage_item__household=household)

    @classmethod
    def as_view(cls, actions=None, **initkwargs):
        view = super().as_view(actions=actions, **initkwargs)
        view.login_not_required = True
        return view


class WhiskyBottleMoveHistoryViewSet(ReadOnlyModelViewSet):
    """Read-only whisky move history — filtered by storage_item's household."""

    authentication_classes = [APIKeyAuthentication]
    permission_classes = [ScopeBasedPermission]
    pagination_class = StandardPagination
    serializer_class = WhiskyBottleMoveHistorySerializer
    queryset = WhiskyBottleMoveHistory.objects.select_related(
        "from_storage", "to_storage"
    ).all()

    def get_queryset(self):
        household = self.request.api_key.household
        return super().get_queryset().filter(storage_item__household=household)

    @classmethod
    def as_view(cls, actions=None, **initkwargs):
        view = super().as_view(actions=actions, **initkwargs)
        view.login_not_required = True
        return view
