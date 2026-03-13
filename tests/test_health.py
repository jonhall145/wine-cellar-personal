import json
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
        assert data == {"status": "ok"}

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
