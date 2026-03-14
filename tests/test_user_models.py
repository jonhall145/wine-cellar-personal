"""Tests for user models (UserSettings, PushSubscription)."""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from wine_cellar.apps.user.models import PushSubscription, UserSettings

User = get_user_model()


@pytest.mark.django_db
class TestUserSettings:
    def test_created_by_user_factory(self, user):
        assert UserSettings.objects.filter(user=user).exists()

    def test_str_representation(self, user):
        settings = user.user_settings
        assert str(settings) == f"Settings for {user}"

    def test_default_currency(self, user):
        settings = user.user_settings
        assert settings.currency == "EUR"

    def test_default_notifications_enabled(self, user):
        settings = user.user_settings
        assert settings.notifications is True

    def test_default_reminder_enabled(self, user):
        settings = user.user_settings
        assert settings.reminder_enabled is True

    def test_default_reminder_years_before(self, user):
        settings = user.user_settings
        assert settings.reminder_years_before == 0

    def test_active_household_set(self, user):
        settings = user.user_settings
        assert settings.active_household is not None

    def test_update_currency(self, user):
        settings = user.user_settings
        settings.currency = "USD"
        settings.save()
        settings.refresh_from_db()
        assert settings.currency == "USD"

    def test_update_language(self, user):
        settings = user.user_settings
        settings.language = "de"
        settings.save()
        settings.refresh_from_db()
        assert settings.language == "de"

    def test_one_to_one_constraint(self, user):
        with pytest.raises(IntegrityError):
            UserSettings.objects.create(user=user)

    def test_cascade_delete_with_user(self, user_factory):
        u = user_factory()
        assert UserSettings.objects.filter(user=u).exists()
        u.delete()
        assert not UserSettings.objects.filter(user_id=u.pk).exists()


@pytest.mark.django_db
class TestPushSubscription:
    def test_create_subscription(self, user):
        sub = PushSubscription.objects.create(
            user=user,
            endpoint="https://push.example.com/sub/123",
            p256dh="test_p256dh_key",
            auth="test_auth_key",
        )
        assert sub.pk is not None
        assert sub.endpoint == "https://push.example.com/sub/123"

    def test_str_representation(self, user):
        sub = PushSubscription.objects.create(
            user=user,
            endpoint="https://push.example.com/sub/123",
            p256dh="key",
            auth="auth",
        )
        assert "Push subscription for" in str(sub)

    def test_to_webpush_dict(self, user):
        sub = PushSubscription.objects.create(
            user=user,
            endpoint="https://push.example.com/sub/123",
            p256dh="test_p256dh",
            auth="test_auth",
        )
        result = sub.to_webpush_dict()
        assert result == {
            "endpoint": "https://push.example.com/sub/123",
            "keys": {
                "p256dh": "test_p256dh",
                "auth": "test_auth",
            },
        }

    def test_unique_together_user_endpoint(self, user):
        PushSubscription.objects.create(
            user=user,
            endpoint="https://push.example.com/sub/1",
            p256dh="key1",
            auth="auth1",
        )
        with pytest.raises(IntegrityError):
            PushSubscription.objects.create(
                user=user,
                endpoint="https://push.example.com/sub/1",
                p256dh="key2",
                auth="auth2",
            )

    def test_same_endpoint_different_users(self, user, user_factory):
        other = user_factory()
        endpoint = "https://push.example.com/sub/shared"
        PushSubscription.objects.create(
            user=user, endpoint=endpoint, p256dh="k1", auth="a1"
        )
        sub2 = PushSubscription.objects.create(
            user=other, endpoint=endpoint, p256dh="k2", auth="a2"
        )
        assert sub2.pk is not None

    def test_cascade_delete_with_user(self, user_factory):
        u = user_factory()
        PushSubscription.objects.create(
            user=u,
            endpoint="https://push.example.com/sub/1",
            p256dh="key",
            auth="auth",
        )
        u.delete()
        assert not PushSubscription.objects.filter(user_id=u.pk).exists()

    def test_created_timestamp(self, user):
        sub = PushSubscription.objects.create(
            user=user,
            endpoint="https://push.example.com/sub/1",
            p256dh="key",
            auth="auth",
        )
        assert sub.created is not None

    def test_multiple_subscriptions_per_user(self, user):
        PushSubscription.objects.create(
            user=user,
            endpoint="https://push.example.com/sub/1",
            p256dh="k1",
            auth="a1",
        )
        PushSubscription.objects.create(
            user=user,
            endpoint="https://push.example.com/sub/2",
            p256dh="k2",
            auth="a2",
        )
        assert PushSubscription.objects.filter(user=user).count() == 2
