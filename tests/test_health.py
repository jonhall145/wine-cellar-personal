import json
from collections import namedtuple
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import Client


@pytest.mark.django_db
class TestHealthCheck:
    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        """Clear cache before each test to avoid cache_page interference."""
        cache.clear()

    def test_returns_200_ok(self, client):
        response = client.get("/health/")
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["status"] == "ok"

    def test_no_auth_required(self):
        client = Client()
        response = client.get("/health/")
        assert response.status_code == 200

    def test_returns_503_on_db_failure(self, client):
        with patch(
            "django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection"
        ) as mock_conn:
            mock_conn.side_effect = Exception("DB down")
            response = client.get("/health/")
            assert response.status_code == 503
            data = json.loads(response.content)
            assert data["status"] == "unhealthy"

    def test_disk_critical_returns_503(self, client):
        DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])
        critical_disk = DiskUsage(
            total=10 * 1024**3, used=9.99 * 1024**3, free=0.01 * 1024**3
        )
        with patch("shutil.disk_usage", return_value=critical_disk):
            response = client.get("/health/")
            assert response.status_code == 503
            data = json.loads(response.content)
            assert data["status"] == "unhealthy"

    def test_disk_check_failure_does_not_fail(self, client):
        with patch("shutil.disk_usage", side_effect=OSError("No such path")):
            response = client.get("/health/")
            assert response.status_code == 200
            data = json.loads(response.content)
            assert data["status"] == "ok"

    def test_healthy_disk_returns_ok(self, client):
        DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])
        healthy_disk = DiskUsage(
            total=100 * 1024**3, used=50 * 1024**3, free=50 * 1024**3
        )
        with patch("shutil.disk_usage", return_value=healthy_disk):
            response = client.get("/health/")
            assert response.status_code == 200
            data = json.loads(response.content)
            assert data["status"] == "ok"


@pytest.mark.django_db
class TestHealthCheckDetailed:
    """Tests for the detailed health check in wine_cellar.apps.wine.views.health."""

    def test_low_disk(self):
        from django.test import RequestFactory

        from wine_cellar.apps.wine.views.health import health_check

        DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])
        low_disk = DiskUsage(total=10 * 1024**3, used=9.5 * 1024**3, free=0.5 * 1024**3)
        factory = RequestFactory()
        request = factory.get("/health-detail/")
        with patch("shutil.disk_usage", return_value=low_disk):
            response = health_check(request)
            data = json.loads(response.content)
            assert data["disk"] == "low"
            assert data["status"] == "ok"
            assert response.status_code == 200

    def test_critical_disk(self):
        from django.test import RequestFactory

        from wine_cellar.apps.wine.views.health import health_check

        DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])
        critical = DiskUsage(
            total=10 * 1024**3, used=9.99 * 1024**3, free=0.01 * 1024**3
        )
        factory = RequestFactory()
        request = factory.get("/health-detail/")
        with patch("shutil.disk_usage", return_value=critical):
            response = health_check(request)
            data = json.loads(response.content)
            assert data["disk"] == "critical"
            assert data["status"] == "unhealthy"
            assert response.status_code == 503

    def test_disk_unknown(self):
        from django.test import RequestFactory

        from wine_cellar.apps.wine.views.health import health_check

        factory = RequestFactory()
        request = factory.get("/health-detail/")
        with patch("shutil.disk_usage", side_effect=OSError("No path")):
            response = health_check(request)
            data = json.loads(response.content)
            assert data["disk"] == "unknown"

    def test_db_failure(self):
        from django.test import RequestFactory

        from wine_cellar.apps.wine.views.health import health_check

        factory = RequestFactory()
        request = factory.get("/health-detail/")
        with patch(
            "django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection",
            side_effect=Exception("DB down"),
        ):
            response = health_check(request)
            data = json.loads(response.content)
            assert data["database"] == "unhealthy"
            assert response.status_code == 503

    def test_includes_disk_free_gb(self):
        from django.test import RequestFactory

        from wine_cellar.apps.wine.views.health import health_check

        DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])
        healthy = DiskUsage(total=100 * 1024**3, used=50 * 1024**3, free=50 * 1024**3)
        factory = RequestFactory()
        request = factory.get("/health-detail/")
        with patch("shutil.disk_usage", return_value=healthy):
            response = health_check(request)
            data = json.loads(response.content)
            assert data["disk_free_gb"] == 50.0
            assert data["disk"] == "ok"
