"""Tests for wine_cellar.apps.core.push – Web Push notification utilities."""

import json
from unittest.mock import MagicMock, patch

import pytest

from wine_cellar.apps.core.push import send_push_notification, send_push_to_user
from wine_cellar.apps.user.models import PushSubscription


@pytest.fixture()
def vapid_settings(settings):
    """Configure VAPID keys for push notification tests."""
    settings.VAPID_PRIVATE_KEY = "test-private-key"
    settings.VAPID_PUBLIC_KEY = "test-public-key"
    settings.VAPID_CLAIMS_EMAIL = "test@example.com"
    return settings


def _make_subscription(user, endpoint="https://push.example.com/sub/1"):
    """Create a PushSubscription for the given user."""
    return PushSubscription.objects.create(
        user=user,
        endpoint=endpoint,
        p256dh="test-p256dh-key",
        auth="test-auth-key",
    )


@pytest.mark.django_db
class TestSendPushNotification:
    """Tests for send_push_notification()."""

    @patch("pywebpush.webpush")
    def test_sends_notification_successfully(self, mock_webpush, user, vapid_settings):
        """Successful send returns True and calls webpush with correct params."""
        sub = _make_subscription(user)
        result = send_push_notification(sub, "Test Title", "Test Body", "/wines/")

        assert result is True
        mock_webpush.assert_called_once()

        call_kwargs = mock_webpush.call_args
        assert call_kwargs.kwargs["subscription_info"] == sub.to_webpush_dict()
        payload = json.loads(call_kwargs.kwargs["data"])
        assert payload["title"] == "Test Title"
        assert payload["body"] == "Test Body"
        assert payload["url"] == "/wines/"
        assert payload["icon"] == "/static/images/pwa-icon-192.png"
        assert call_kwargs.kwargs["vapid_private_key"] == "test-private-key"
        assert call_kwargs.kwargs["vapid_claims"] == {
            "sub": "mailto:test@example.com",
        }

    @patch("pywebpush.webpush")
    def test_handles_webpush_exception(self, mock_webpush, user, vapid_settings):
        """Non-expired WebPushException returns False without deleting subscription."""
        from pywebpush import WebPushException

        response = MagicMock()
        response.status_code = 500
        mock_webpush.side_effect = WebPushException("Server error", response=response)

        sub = _make_subscription(user)
        result = send_push_notification(sub, "Title", "Body")

        assert result is False
        assert PushSubscription.objects.filter(pk=sub.pk).exists()

    @patch("pywebpush.webpush")
    def test_deletes_expired_subscription_410(self, mock_webpush, user, vapid_settings):
        """410 response deletes the subscription and returns False."""
        from pywebpush import WebPushException

        response = MagicMock()
        response.status_code = 410
        mock_webpush.side_effect = WebPushException("Gone", response=response)

        sub = _make_subscription(user)
        sub_pk = sub.pk
        result = send_push_notification(sub, "Title", "Body")

        assert result is False
        assert not PushSubscription.objects.filter(pk=sub_pk).exists()

    @patch("pywebpush.webpush")
    def test_deletes_expired_subscription_404(self, mock_webpush, user, vapid_settings):
        """404 response also triggers subscription cleanup."""
        from pywebpush import WebPushException

        response = MagicMock()
        response.status_code = 404
        mock_webpush.side_effect = WebPushException("Not found", response=response)

        sub = _make_subscription(user)
        sub_pk = sub.pk
        result = send_push_notification(sub, "Title", "Body")

        assert result is False
        assert not PushSubscription.objects.filter(pk=sub_pk).exists()

    def test_missing_vapid_keys_returns_false(self, user, settings):
        """Returns False immediately when VAPID keys are not configured."""
        settings.VAPID_PRIVATE_KEY = ""
        settings.VAPID_PUBLIC_KEY = ""

        sub = _make_subscription(user)
        result = send_push_notification(sub, "Title", "Body")

        assert result is False

    def test_missing_vapid_private_key_returns_false(self, user, settings):
        """Returns False when only the private key is missing."""
        settings.VAPID_PRIVATE_KEY = ""
        settings.VAPID_PUBLIC_KEY = "some-key"

        sub = _make_subscription(user)
        result = send_push_notification(sub, "Title", "Body")

        assert result is False

    @patch("pywebpush.webpush", side_effect=RuntimeError("unexpected"))
    def test_handles_unexpected_exception(self, mock_webpush, user, vapid_settings):
        """Unexpected exceptions are caught and return False."""
        sub = _make_subscription(user)
        result = send_push_notification(sub, "Title", "Body")

        assert result is False
        assert PushSubscription.objects.filter(pk=sub.pk).exists()


@pytest.mark.django_db
class TestSendPushToUser:
    """Tests for send_push_to_user()."""

    @patch("pywebpush.webpush")
    def test_sends_to_all_user_subscriptions(self, mock_webpush, user, vapid_settings):
        """Sends notification to every subscription and returns count."""
        _make_subscription(user, endpoint="https://push.example.com/sub/1")
        _make_subscription(user, endpoint="https://push.example.com/sub/2")
        _make_subscription(user, endpoint="https://push.example.com/sub/3")

        sent = send_push_to_user(user, "Title", "Body", "/url/")

        assert sent == 3
        assert mock_webpush.call_count == 3

    def test_no_subscriptions_returns_zero(self, user):
        """Returns 0 when user has no push subscriptions."""
        sent = send_push_to_user(user, "Title", "Body")

        assert sent == 0

    @patch("pywebpush.webpush")
    def test_continues_when_one_subscription_fails(
        self, mock_webpush, user, vapid_settings
    ):
        """Failure on one subscription doesn't prevent sending to others."""
        from pywebpush import WebPushException

        _make_subscription(user, endpoint="https://push.example.com/sub/1")
        _make_subscription(user, endpoint="https://push.example.com/sub/2")
        _make_subscription(user, endpoint="https://push.example.com/sub/3")

        response = MagicMock()
        response.status_code = 500
        mock_webpush.side_effect = [
            None,  # first succeeds
            WebPushException("fail", response=response),  # second fails
            None,  # third succeeds
        ]

        sent = send_push_to_user(user, "Title", "Body")

        assert sent == 2
        assert mock_webpush.call_count == 3
