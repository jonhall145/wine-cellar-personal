"""Tests for PWA endpoints: manifest, service worker, offline, sync API, push."""

import json
from http import HTTPStatus

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestManifest:
    def test_manifest_unauthenticated(self, client):
        """Manifest is publicly accessible (login_not_required)."""
        r = client.get(reverse("pwa-manifest"))
        assert r.status_code == HTTPStatus.OK
        data = json.loads(r.content)
        assert data["name"] == "Wine Cellar"
        assert data["short_name"] == "Wine"
        assert data["display"] == "standalone"
        assert data["theme_color"] == "#019603"
        assert len(data["icons"]) == 3

    def test_manifest_icons_have_correct_sizes(self, client):
        r = client.get(reverse("pwa-manifest"))
        data = json.loads(r.content)
        sizes = {icon["sizes"] for icon in data["icons"]}
        assert "192x192" in sizes
        assert "512x512" in sizes

    def test_manifest_content_type(self, client):
        r = client.get(reverse("pwa-manifest"))
        assert "application/json" in r["Content-Type"]


@pytest.mark.django_db
class TestServiceWorker:
    def test_sw_unauthenticated(self, client):
        r = client.get(reverse("pwa-service-worker"))
        assert r.status_code == HTTPStatus.OK

    def test_sw_content_type(self, client):
        r = client.get(reverse("pwa-service-worker"))
        assert r["Content-Type"] == "application/javascript"

    def test_sw_has_scope_header(self, client):
        r = client.get(reverse("pwa-service-worker"))
        assert r["Service-Worker-Allowed"] == "/"

    def test_sw_contains_cache_logic(self, client):
        r = client.get(reverse("pwa-service-worker"))
        content = r.content.decode()
        assert "CACHE_NAME" in content
        assert "caches.open" in content
        assert "self.addEventListener" in content


@pytest.mark.django_db
class TestOfflinePage:
    def test_offline_unauthenticated(self, client):
        r = client.get(reverse("pwa-offline"))
        assert r.status_code == HTTPStatus.OK

    def test_offline_contains_retry(self, client):
        r = client.get(reverse("pwa-offline"))
        content = r.content.decode()
        assert "offline" in content.lower()


@pytest.mark.django_db
class TestCellarSyncAPI:
    def test_requires_authentication(self, client):
        r = client.get(reverse("api-cellar-sync"))
        assert r.status_code == HTTPStatus.FOUND  # redirect to login

    def test_returns_json(self, client, user):
        client.force_login(user)
        r = client.get(reverse("api-cellar-sync"))
        assert r.status_code == HTTPStatus.OK
        assert "application/json" in r["Content-Type"]

    def test_response_structure(self, client, user):
        client.force_login(user)
        r = client.get(reverse("api-cellar-sync"))
        data = json.loads(r.content)
        assert "beverages" in data
        assert "stock_items" in data
        assert "storages" in data
        assert "app_type" in data
        assert "currency" in data
        assert data["is_incremental"] is False

    def test_returns_wines(self, client, user, wine):
        client.force_login(user)
        r = client.get(reverse("api-cellar-sync"))
        data = json.loads(r.content)
        assert len(data["beverages"]) == 1
        assert data["beverages"][0]["name"] == wine.name
        assert data["beverages"][0]["id"] == wine.pk

    def test_returns_stock_items(self, client, user, storage_item):
        client.force_login(user)
        r = client.get(reverse("api-cellar-sync"))
        data = json.loads(r.content)
        assert len(data["stock_items"]) == 1
        assert data["stock_items"][0]["id"] == storage_item.pk

    def test_returns_storages(self, client, user, storage):
        client.force_login(user)
        r = client.get(reverse("api-cellar-sync"))
        data = json.loads(r.content)
        assert len(data["storages"]) >= 1
        names = [s["name"] for s in data["storages"]]
        assert storage.name in names

    def test_incremental_sync(self, client, user, wine):
        client.force_login(user)
        # Full sync first
        r = client.get(reverse("api-cellar-sync"))
        data = json.loads(r.content)
        assert data["is_incremental"] is False
        assert len(data["beverages"]) == 1

        # Incremental with future date returns nothing
        r = client.get(reverse("api-cellar-sync") + "?since=2099-01-01T00:00:00")
        data = json.loads(r.content)
        assert data["is_incremental"] is True
        assert len(data["beverages"]) == 0

    def test_excludes_deleted_wines(self, client, user, wine):
        wine.deleted = True
        wine.save()
        client.force_login(user)
        r = client.get(reverse("api-cellar-sync"))
        data = json.loads(r.content)
        assert len(data["beverages"]) == 0

    def test_post_not_allowed(self, client, user):
        client.force_login(user)
        r = client.post(reverse("api-cellar-sync"))
        assert r.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_invalid_since_returns_400(self, client, user):
        client.force_login(user)
        r = client.get(reverse("api-cellar-sync") + "?since=not-a-date")
        assert r.status_code == HTTPStatus.BAD_REQUEST
        data = json.loads(r.content)
        assert "error" in data


@pytest.mark.django_db
class TestPushSubscribe:
    def test_requires_auth(self, client):
        r = client.post(
            reverse("api-push-subscribe"),
            data=json.dumps({"endpoint": "https://example.com"}),
            content_type="application/json",
        )
        assert r.status_code == HTTPStatus.FOUND

    def test_subscribe(self, client, user):
        client.force_login(user)
        payload = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
            "keys": {"p256dh": "test-p256dh-key", "auth": "test-auth-key"},
        }
        r = client.post(
            reverse("api-push-subscribe"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == HTTPStatus.OK
        data = json.loads(r.content)
        assert data["ok"] is True

        from wine_cellar.apps.user.models import PushSubscription

        sub = PushSubscription.objects.get(user=user)
        assert sub.endpoint == payload["endpoint"]
        assert sub.p256dh == "test-p256dh-key"
        assert sub.auth == "test-auth-key"

    def test_subscribe_missing_fields(self, client, user):
        client.force_login(user)
        r = client.post(
            reverse("api-push-subscribe"),
            data=json.dumps({"endpoint": "https://example.com"}),
            content_type="application/json",
        )
        assert r.status_code == HTTPStatus.BAD_REQUEST

    def test_subscribe_invalid_json(self, client, user):
        client.force_login(user)
        r = client.post(
            reverse("api-push-subscribe"),
            data="not json",
            content_type="application/json",
        )
        assert r.status_code == HTTPStatus.BAD_REQUEST

    def test_subscribe_update_existing(self, client, user):
        client.force_login(user)
        endpoint = "https://fcm.googleapis.com/fcm/send/abc123"
        payload = {
            "endpoint": endpoint,
            "keys": {"p256dh": "key1", "auth": "auth1"},
        }
        client.post(
            reverse("api-push-subscribe"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        # Update with new keys
        payload["keys"] = {"p256dh": "key2", "auth": "auth2"}
        client.post(
            reverse("api-push-subscribe"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        from wine_cellar.apps.user.models import PushSubscription

        assert PushSubscription.objects.filter(user=user).count() == 1
        sub = PushSubscription.objects.get(user=user)
        assert sub.p256dh == "key2"


@pytest.mark.django_db
class TestPushUnsubscribe:
    def test_unsubscribe(self, client, user):
        from wine_cellar.apps.user.models import PushSubscription

        PushSubscription.objects.create(
            user=user,
            endpoint="https://fcm.googleapis.com/fcm/send/abc123",
            p256dh="key",
            auth="auth",
        )
        client.force_login(user)
        r = client.post(
            reverse("api-push-unsubscribe"),
            data=json.dumps({"endpoint": "https://fcm.googleapis.com/fcm/send/abc123"}),
            content_type="application/json",
        )
        assert r.status_code == HTTPStatus.OK
        assert PushSubscription.objects.filter(user=user).count() == 0

    def test_unsubscribe_nonexistent(self, client, user):
        client.force_login(user)
        r = client.post(
            reverse("api-push-unsubscribe"),
            data=json.dumps({"endpoint": "https://nonexistent.com"}),
            content_type="application/json",
        )
        assert r.status_code == HTTPStatus.OK


@pytest.mark.django_db
class TestVapidPublicKey:
    def test_returns_key(self, client, user):
        client.force_login(user)
        r = client.get(reverse("api-vapid-public-key"))
        assert r.status_code == HTTPStatus.OK
        data = json.loads(r.content)
        assert "public_key" in data
