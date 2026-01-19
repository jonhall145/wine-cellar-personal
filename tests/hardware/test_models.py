"""Tests for hardware app models."""

import pytest
from django.db import IntegrityError


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
