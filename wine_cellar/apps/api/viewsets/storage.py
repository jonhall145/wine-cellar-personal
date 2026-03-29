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
