"""Tests for hardware API endpoints."""

import json
from http import HTTPStatus

import pytest
from django.urls import reverse

from wine_cellar.apps.hardware.models import (
    OfflineOperation,
    ReviewStatus,
)


@pytest.mark.django_db
class TestHealthCheck:
    """Tests for API health check endpoint."""

    def test_health_check(self, client):
        """Test health check returns OK."""
        url = reverse("hardware-api:health")
        response = client.get(url)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data


@pytest.mark.django_db
class TestHardwareAuth:
    """Tests for hardware authentication."""

    def test_missing_token(self, client):
        """Test request without token is rejected."""
        url = reverse("hardware-api:pending-reviews")
        response = client.get(url)
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_invalid_token(self, client):
        """Test request with invalid token is rejected."""
        url = reverse("hardware-api:pending-reviews")
        response = client.get(url, HTTP_AUTHORIZATION="Token invalid-token")
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_valid_token(self, client, hardware_device_factory):
        """Test request with valid token succeeds."""
        device = hardware_device_factory()
        url = reverse("hardware-api:pending-reviews")
        response = client.get(url, HTTP_AUTHORIZATION=f"Token {device.api_token}")
        assert response.status_code == HTTPStatus.OK

    def test_inactive_device_token(self, client, hardware_device_factory):
        """Test request with inactive device token is rejected."""
        device = hardware_device_factory(is_active=False)
        url = reverse("hardware-api:pending-reviews")
        response = client.get(url, HTTP_AUTHORIZATION=f"Token {device.api_token}")
        assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.django_db
class TestPositionChangeAPI:
    """Tests for position change API endpoints."""

    def test_report_position_change(
        self, client, hardware_device_factory, storage_factory, wine_factory
    ):
        """Test reporting a position change."""
        device = hardware_device_factory()
        storage = storage_factory(user=device.user)
        wine = wine_factory(user=device.user)

        url = reverse("hardware-api:position-change")
        data = {
            "rack_id": storage.pk,
            "row": 2,
            "col": 3,
            "change_type": "added",
            "wine_id": wine.pk,
            "confidence": 0.75,
        }
        response = client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {device.api_token}",
        )
        assert response.status_code == HTTPStatus.OK
        result = response.json()
        assert "id" in result
        assert result["status"] == ReviewStatus.PENDING
        assert result["auto_applied"] is False

    def test_report_high_confidence_auto_applies(
        self, client, hardware_device_factory, storage_factory, wine_factory
    ):
        """Test high confidence changes are auto-applied."""
        device = hardware_device_factory()
        storage = storage_factory(user=device.user)
        wine = wine_factory(user=device.user)

        url = reverse("hardware-api:position-change")
        data = {
            "rack_id": storage.pk,
            "row": 2,
            "col": 3,
            "change_type": "added",
            "wine_id": wine.pk,
            "confidence": 0.95,  # High confidence
        }
        response = client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {device.api_token}",
        )
        assert response.status_code == HTTPStatus.OK
        result = response.json()
        assert result["status"] == ReviewStatus.AUTO_APPLIED
        assert result["auto_applied"] is True

    def test_get_pending_reviews(
        self, client, hardware_device_factory, position_change_review_factory
    ):
        """Test getting pending reviews."""
        device = hardware_device_factory()
        # Create reviews for this user
        review1 = position_change_review_factory(
            user=device.user, status=ReviewStatus.PENDING
        )
        review2 = position_change_review_factory(
            user=device.user, status=ReviewStatus.PENDING
        )
        # Create review for another user (should not be returned)
        position_change_review_factory(status=ReviewStatus.PENDING)

        url = reverse("hardware-api:pending-reviews")
        response = client.get(url, HTTP_AUTHORIZATION=f"Token {device.api_token}")
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data["reviews"]) == 2
        review_ids = [r["id"] for r in data["reviews"]]
        assert review1.pk in review_ids
        assert review2.pk in review_ids


@pytest.mark.django_db
class TestReviewApproval:
    """Tests for review approval/rejection."""

    def test_approve_review(self, client, user, position_change_review_factory):
        """Test approving a review."""
        client.force_login(user)
        review = position_change_review_factory(user=user, row=2, column=3)

        url = reverse("hardware-api:approve-review", kwargs={"review_id": review.pk})
        data = {"row": 2, "column": 3}
        response = client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
        )
        assert response.status_code == HTTPStatus.OK

        review.refresh_from_db()
        assert review.status == ReviewStatus.APPROVED
        assert review.final_row == 2
        assert review.final_column == 3
        assert review.reviewed_at is not None

    def test_approve_review_with_correction(
        self, client, user, position_change_review_factory
    ):
        """Test approving with corrected position."""
        client.force_login(user)
        review = position_change_review_factory(user=user, row=2, column=3)

        url = reverse("hardware-api:approve-review", kwargs={"review_id": review.pk})
        data = {"row": 4, "column": 5}  # Corrected position
        response = client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
        )
        assert response.status_code == HTTPStatus.OK

        review.refresh_from_db()
        assert review.final_row == 4
        assert review.final_column == 5

    def test_reject_review(self, client, user, position_change_review_factory):
        """Test rejecting a review."""
        client.force_login(user)
        review = position_change_review_factory(user=user)

        url = reverse("hardware-api:reject-review", kwargs={"review_id": review.pk})
        response = client.post(url)
        assert response.status_code == HTTPStatus.OK

        review.refresh_from_db()
        assert review.status == ReviewStatus.REJECTED
        assert review.reviewed_at is not None

    def test_cannot_approve_other_user_review(
        self, client, user, position_change_review_factory
    ):
        """Test cannot approve another user's review."""
        client.force_login(user)
        # Review belongs to a different user
        review = position_change_review_factory()

        url = reverse("hardware-api:approve-review", kwargs={"review_id": review.pk})
        response = client.post(
            url,
            data=json.dumps({"row": 1, "column": 1}),
            content_type="application/json",
        )
        assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.django_db
class TestSyncOperations:
    """Tests for sync operations endpoint."""

    def test_sync_operations(
        self, client, hardware_device_factory, storage_factory, wine_factory
    ):
        """Test syncing offline operations."""
        device = hardware_device_factory()
        storage = storage_factory(user=device.user)
        wine = wine_factory(user=device.user)

        url = reverse("hardware-api:sync")
        data = {
            "operations": [
                {
                    "operation_type": "add_wine",
                    "data": {
                        "wine_id": wine.pk,
                        "rack_id": storage.pk,
                        "row": 1,
                        "col": 1,
                    },
                    "timestamp": "2024-01-01T12:00:00Z",
                }
            ]
        }
        response = client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {device.api_token}",
        )
        assert response.status_code == HTTPStatus.OK
        result = response.json()
        assert result["synced"] == 1
        assert result["results"][0]["success"] is True

        # Verify operation was recorded
        assert OfflineOperation.objects.filter(device=device).count() == 1


@pytest.mark.django_db
class TestWineByBarcode:
    """Tests for wine lookup by barcode."""

    def test_wine_found(self, client, hardware_device_factory, wine_factory):
        """Test looking up wine by barcode."""
        device = hardware_device_factory()
        wine = wine_factory(user=device.user, barcode="1234567890")

        url = reverse("hardware-api:wine-by-barcode", kwargs={"barcode": "1234567890"})
        response = client.get(url, HTTP_AUTHORIZATION=f"Token {device.api_token}")
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["id"] == wine.pk
        assert data["barcode"] == "1234567890"

    def test_wine_not_found(self, client, hardware_device_factory):
        """Test looking up non-existent barcode."""
        device = hardware_device_factory()

        url = reverse("hardware-api:wine-by-barcode", kwargs={"barcode": "9999999999"})
        response = client.get(url, HTTP_AUTHORIZATION=f"Token {device.api_token}")
        assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.django_db
class TestRackPositions:
    """Tests for rack position endpoints."""

    def test_get_rack_positions(
        self,
        client,
        hardware_device_factory,
        storage_factory,
        storage_item_factory,
        wine_factory,
    ):
        """Test getting all positions for a rack."""
        device = hardware_device_factory()
        storage = storage_factory(user=device.user, rows=3, columns=3)
        wine = wine_factory(user=device.user)
        storage_item_factory(storage=storage, wine=wine, row=1, column=2)

        url = reverse("hardware-api:rack-positions", kwargs={"rack_id": storage.pk})
        response = client.get(url, HTTP_AUTHORIZATION=f"Token {device.api_token}")
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["rack_id"] == storage.pk
        assert data["rows"] == 3
        assert data["columns"] == 3
        assert len(data["positions"]) == 9  # 3x3 grid

        # Find the occupied position
        occupied = [p for p in data["positions"] if not p["is_empty"]]
        assert len(occupied) == 1
        assert occupied[0]["row"] == 1
        assert occupied[0]["col"] == 2
        assert occupied[0]["wine_id"] == wine.pk

    def test_add_wine_to_position(
        self, client, hardware_device_factory, storage_factory, wine_factory
    ):
        """Test adding wine to a position."""
        device = hardware_device_factory()
        storage = storage_factory(user=device.user)
        wine = wine_factory(user=device.user)

        url = reverse("hardware-api:storage-add")
        data = {
            "wine_id": wine.pk,
            "rack_id": storage.pk,
            "row": 2,
            "col": 3,
        }
        response = client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {device.api_token}",
        )
        assert response.status_code == HTTPStatus.OK
        result = response.json()
        assert result["wine_id"] == wine.pk
        assert result["row"] == 2
        assert result["col"] == 3
        assert result["is_empty"] is False

    def test_remove_wine_from_position(
        self,
        client,
        hardware_device_factory,
        storage_factory,
        storage_item_factory,
        wine_factory,
    ):
        """Test removing wine from a position."""
        device = hardware_device_factory()
        storage = storage_factory(user=device.user)
        wine = wine_factory(user=device.user)
        storage_item_factory(storage=storage, wine=wine, row=1, column=1)

        url = reverse("hardware-api:storage-remove")
        data = {
            "rack_id": storage.pk,
            "row": 1,
            "col": 1,
        }
        response = client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {device.api_token}",
        )
        assert response.status_code == HTTPStatus.OK
        result = response.json()
        assert result["wine"]["id"] == wine.pk
