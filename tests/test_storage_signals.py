"""Tests for storage signals (default storage creation)."""

import pytest
from django.contrib.auth import get_user_model

from wine_cellar.apps.storage.models import Storage

User = get_user_model()


@pytest.mark.django_db
class TestCreateStorageSignal:
    """Test that a default storage is created when a new user is created."""

    def test_default_storage_created_for_new_user(self, user):
        storages = Storage.objects.filter(user=user)
        assert storages.exists()

    def test_default_storage_has_expected_name(self, user):
        storage = Storage.objects.filter(user=user).first()
        assert storage.name == "Default Shelf"

    def test_default_storage_has_zero_grid(self, user):
        storage = Storage.objects.filter(user=user).first()
        assert storage.rows == 0
        assert storage.columns == 0

    def test_default_storage_has_location(self, user):
        storage = Storage.objects.filter(user=user).first()
        assert storage.location == "Home"

    def test_default_storage_linked_to_household(self, user):
        storage = Storage.objects.filter(user=user).first()
        assert storage.household is not None
        assert storage.household == user.user_settings.active_household

    def test_multiple_users_get_separate_storages(self, user, user_factory):
        other_user = user_factory()
        user_storages = Storage.objects.filter(user=user)
        other_storages = Storage.objects.filter(user=other_user)
        assert user_storages.exists()
        assert other_storages.exists()
        assert set(user_storages.values_list("pk", flat=True)) != set(
            other_storages.values_list("pk", flat=True)
        )
