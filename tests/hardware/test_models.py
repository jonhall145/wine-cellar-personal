"""Tests for hardware app models."""

import pytest
from django.db import IntegrityError

from wine_cellar.apps.hardware.models import ChangeType, ReviewStatus


@pytest.mark.django_db
class TestHardwareDevice:
    """Tests for HardwareDevice model."""

    def test_create_device(self, hardware_device_factory):
        """Test creating a hardware device."""
        device = hardware_device_factory()
        assert device.pk is not None
        assert device.is_active is True
        assert device.api_token is not None
        assert len(device.api_token) > 20

    def test_device_str(self, hardware_device_factory):
        """Test string representation."""
        device = hardware_device_factory(name="Kitchen Pi", device_id="pi-kitchen-001")
        assert "Kitchen Pi" in str(device)
        assert "pi-kitchen-001" in str(device)

    def test_device_id_unique(self, hardware_device_factory):
        """Test device_id must be unique."""
        hardware_device_factory(device_id="unique-id-123")
        with pytest.raises(IntegrityError):
            hardware_device_factory(device_id="unique-id-123")

    def test_api_token_unique(self, hardware_device_factory):
        """Test api_token must be unique."""
        device1 = hardware_device_factory()
        with pytest.raises(IntegrityError):
            hardware_device_factory(api_token=device1.api_token)


@pytest.mark.django_db
class TestPositionChangeReview:
    """Tests for PositionChangeReview model."""

    def test_create_review(self, position_change_review_factory):
        """Test creating a position change review."""
        review = position_change_review_factory()
        assert review.pk is not None
        assert review.status == ReviewStatus.PENDING
        assert review.change_type == ChangeType.ADDED

    def test_review_str(self, position_change_review_factory, storage_factory):
        """Test string representation."""
        storage = storage_factory(name="Wine Rack")
        review = position_change_review_factory(
            storage=storage,
            row=3,
            column=5,
            change_type=ChangeType.REMOVED,
        )
        result = str(review)
        assert "Bottle Removed" in result
        assert "Wine Rack" in result
        assert "(3, 5)" in result

    def test_review_status_choices(self, position_change_review_factory):
        """Test different review status values."""
        for status in ReviewStatus:
            review = position_change_review_factory(status=status)
            assert review.status == status

    def test_review_change_type_choices(self, position_change_review_factory):
        """Test different change type values."""
        for change_type in ChangeType:
            review = position_change_review_factory(change_type=change_type)
            assert review.change_type == change_type


@pytest.mark.django_db
class TestRackSnapshot:
    """Tests for RackSnapshot model."""

    def test_create_snapshot(self, rack_snapshot_factory):
        """Test creating a rack snapshot."""
        snapshot = rack_snapshot_factory()
        assert snapshot.pk is not None
        assert snapshot.grid_state is not None

    def test_snapshot_str(self, rack_snapshot_factory, storage_factory):
        """Test string representation."""
        storage = storage_factory(name="Cellar Rack")
        snapshot = rack_snapshot_factory(storage=storage)
        result = str(snapshot)
        assert "Cellar Rack" in result


@pytest.mark.django_db
class TestOfflineOperation:
    """Tests for OfflineOperation model."""

    def test_create_operation(self, offline_operation_factory):
        """Test creating an offline operation."""
        operation = offline_operation_factory()
        assert operation.pk is not None
        assert operation.applied is False

    def test_operation_str(self, offline_operation_factory, hardware_device_factory):
        """Test string representation."""
        device = hardware_device_factory(name="Garage Pi")
        operation = offline_operation_factory(
            device=device,
            operation_type="remove_wine",
        )
        result = str(operation)
        assert "remove_wine" in result
        assert "Garage Pi" in result


@pytest.mark.django_db
class TestRackVisionConfig:
    """Tests for RackVisionConfig model."""

    def test_create_config(self, rack_vision_config_factory):
        """Test creating a rack vision config."""
        config = rack_vision_config_factory()
        assert config.pk is not None
        assert config.auto_apply_threshold == 90
        assert config.enable_hourly_snapshots is True
        assert config.enable_daily_reconciliation is True

    def test_config_str(self, rack_vision_config_factory, storage_factory):
        """Test string representation."""
        storage = storage_factory(name="Main Cellar")
        config = rack_vision_config_factory(storage=storage)
        assert "Main Cellar" in str(config)

    def test_config_str_no_storage(self, rack_vision_config_factory):
        """Test string representation when no storage is set."""
        config = rack_vision_config_factory(storage=None)
        assert "Not configured" in str(config)

    def test_one_config_per_user(self, rack_vision_config_factory, user):
        """Test only one config per user is allowed."""
        rack_vision_config_factory(user=user)
        with pytest.raises(IntegrityError):
            rack_vision_config_factory(user=user)
