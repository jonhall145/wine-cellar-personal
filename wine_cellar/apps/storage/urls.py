from django.urls import path

from wine_cellar.apps.storage.views import (
    StorageCreateView,
    StorageDeleteView,
    StorageDetailView,
    StorageListView,
    StorageUpdateView,
    move_bottle,
    storage_grid_data,
    storage_move_down,
    storage_move_up,
)

urlpatterns = [
    path("storages/", StorageListView.as_view(), name="storage-list"),
    path("storage/<int:pk>/", StorageDetailView.as_view(), name="storage-detail"),
    path("storage/add/", StorageCreateView.as_view(), name="storage-add"),
    path(
        "storage/delete/<int:pk>/", StorageDeleteView.as_view(), name="storage-delete"
    ),
    path("storage/edit/<int:pk>/", StorageUpdateView.as_view(), name="storage-edit"),
    path("storage/move-up/<int:pk>/", storage_move_up, name="storage-move-up"),
    path("storage/move-down/<int:pk>/", storage_move_down, name="storage-move-down"),
    path("api/storage/grid-data/", storage_grid_data, name="storage-grid-data"),
    path("api/storage/move-bottle/", move_bottle, name="storage-move-bottle"),
]
