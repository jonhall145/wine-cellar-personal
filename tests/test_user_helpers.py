"""Tests for user view helper functions."""

import pytest
from django.contrib.auth import get_user_model

from wine_cellar.apps.user.models import UserSettings
from wine_cellar.apps.user.views import get_active_household, get_user_settings

User = get_user_model()


@pytest.mark.django_db
class TestGetUserSettings:
    def test_returns_existing_settings(self, user):
        result = get_user_settings(user)
        assert isinstance(result, UserSettings)
        assert result.user == user

    def test_creates_settings_if_missing(self, user):
        UserSettings.objects.filter(user=user).delete()
        # Clear the cache
        if hasattr(user, "_cached_settings"):
            del user._cached_settings
        result = get_user_settings(user)
        assert isinstance(result, UserSettings)
        assert result.user == user

    def test_caches_on_user_object(self, user):
        if hasattr(user, "_cached_settings"):
            del user._cached_settings
        result1 = get_user_settings(user)
        result2 = get_user_settings(user)
        assert result1 is result2
        assert hasattr(user, "_cached_settings")

    def test_cache_avoids_extra_queries(self, user, django_assert_num_queries):
        if hasattr(user, "_cached_settings"):
            del user._cached_settings
        # First call may query
        get_user_settings(user)
        # Second call should use cache (0 queries)
        with django_assert_num_queries(0):
            get_user_settings(user)


@pytest.mark.django_db
class TestGetActiveHousehold:
    def test_returns_household(self, user):
        result = get_active_household(user)
        assert result is not None
        assert result == user.user_settings.active_household

    def test_caches_on_user_object(self, user):
        if hasattr(user, "_cached_household"):
            del user._cached_household
        result1 = get_active_household(user)
        result2 = get_active_household(user)
        assert result1 is result2
        assert hasattr(user, "_cached_household")

    def test_returns_none_when_no_household(self, user):
        settings = user.user_settings
        settings.active_household = None
        settings.save()
        if hasattr(user, "_cached_household"):
            del user._cached_household
        if hasattr(user, "_cached_settings"):
            del user._cached_settings
        result = get_active_household(user)
        assert result is None
