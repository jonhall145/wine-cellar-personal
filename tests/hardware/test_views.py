"""Tests for hardware web views."""

from http import HTTPStatus

import pytest
from django.urls import reverse
from pytest_django.asserts import assertRedirects, assertTemplateUsed

from wine_cellar.apps.hardware.models import (
    HardwareDevice,
)


@pytest.mark.django_db
class TestDeviceSettingsView:
    """Tests for DeviceSettingsView."""

    def test_unauthenticated_redirect(self, client):
        """Test unauthenticated users are redirected to login."""
        url = reverse("hardware:device-settings")
        response = client.get(url)
        assert response.status_code == HTTPStatus.FOUND
        assert "login" in response.url

    def test_authenticated_access(self, client, user):
        """Test authenticated users can access the page."""
        client.force_login(user)
        url = reverse("hardware:device-settings")
        response = client.get(url)
        assert response.status_code == HTTPStatus.OK
        assertTemplateUsed(response, "device_settings.html")

    def test_shows_user_devices(self, client, user, hardware_device_factory):
        """Test page shows devices for the user."""
        client.force_login(user)
        device1 = hardware_device_factory(user=user)
        device2 = hardware_device_factory(user=user)
        # Other user's device should not appear
        hardware_device_factory()

        url = reverse("hardware:device-settings")
        response = client.get(url)
        assert response.status_code == HTTPStatus.OK
        device_ids = [d.pk for d in response.context["devices"]]
        assert device1.pk in device_ids
        assert device2.pk in device_ids
        assert len(device_ids) == 2

    def test_register_device(self, client, user, storage_factory):
        """Test registering a new device."""
        client.force_login(user)
        storage = storage_factory(user=user)

        url = reverse("hardware:device-settings")
        data = {
            "action": "register",
            "name": "New Pi Device",
            "device_id": "pi-new-device",
            "storage_id": storage.pk,
        }
        response = client.post(url, data)
        assertRedirects(response, url)

        # Verify device was created
        device = HardwareDevice.objects.get(device_id="pi-new-device")
        assert device.name == "New Pi Device"
        assert device.user == user
        assert device.storage == storage

    def test_register_device_without_storage(self, client, user):
        """Test registering a device without assigning storage."""
        client.force_login(user)

        url = reverse("hardware:device-settings")
        data = {
            "action": "register",
            "name": "Standalone Pi",
            "device_id": "pi-standalone",
        }
        response = client.post(url, data)
        assertRedirects(response, url)

        device = HardwareDevice.objects.get(device_id="pi-standalone")
        assert device.storage is None

    def test_register_device_missing_id(self, client, user):
        """Test registering without device_id shows error."""
        client.force_login(user)

        url = reverse("hardware:device-settings")
        data = {
            "action": "register",
            "name": "Bad Device",
        }
        response = client.post(url, data, follow=True)
        # Should redirect back with error message
        assert response.status_code == HTTPStatus.OK
        assert not HardwareDevice.objects.filter(name="Bad Device").exists()

    def test_register_duplicate_device_id(self, client, user, hardware_device_factory):
        """Test registering duplicate device_id shows error."""
        client.force_login(user)
        hardware_device_factory(device_id="existing-device")

        url = reverse("hardware:device-settings")
        data = {
            "action": "register",
            "name": "Duplicate Device",
            "device_id": "existing-device",
        }
        response = client.post(url, data, follow=True)
        assert response.status_code == HTTPStatus.OK
        # Only one device with this ID should exist
        assert HardwareDevice.objects.filter(device_id="existing-device").count() == 1

    def test_toggle_device(self, client, user, hardware_device_factory):
        """Test toggling device active status."""
        client.force_login(user)
        device = hardware_device_factory(user=user, is_active=True)

        url = reverse("hardware:device-settings")
        data = {
            "action": "toggle",
            "device_pk": device.pk,
        }
        response = client.post(url, data)
        assertRedirects(response, url)

        device.refresh_from_db()
        assert device.is_active is False

        # Toggle again
        response = client.post(url, data)
        device.refresh_from_db()
        assert device.is_active is True

    def test_delete_device(self, client, user, hardware_device_factory):
        """Test deleting a device."""
        client.force_login(user)
        device = hardware_device_factory(user=user)
        device_pk = device.pk

        url = reverse("hardware:device-settings")
        data = {
            "action": "delete",
            "device_pk": device.pk,
        }
        response = client.post(url, data)
        assertRedirects(response, url)

        assert not HardwareDevice.objects.filter(pk=device_pk).exists()
