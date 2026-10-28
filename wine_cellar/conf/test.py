"""
Test settings for Wine Cellar.

This module imports all base settings and overrides test-specific values.
"""

import tempfile

# Import all base settings explicitly
from wine_cellar.conf.settings import (
    ACCOUNT_ADAPTER,
    ALLOWED_HOSTS,
    ANTHROPIC_API_KEY,
    AUTH_PASSWORD_VALIDATORS,
    AUTHENTICATION_BACKENDS,
    BASE_DIR,
    CELLAR_APP_TYPE,
    CSRF_TRUSTED_ORIGINS,
    CURRENCIES,
    CURRENCY_SYMBOLS,
    DATABASES,
    DEBUG,
    DEFAULT_AUTO_FIELD,
    DEFAULT_WINE_IMAGE,
    EMAIL_BACKEND,
    INSTALLED_APPS,
    LANGUAGE_CODE,
    LOG_LEVEL,
    LOGGING,
    LOGIN_REDIRECT_URL,
    LOGOUT_REDIRECT_URL,
    MAP_BASEURL,
    MEDIA_URL,
    MIDDLEWARE,
    REST_FRAMEWORK,
    ROOT_DIR,
    ROOT_URLCONF,
    SECRET_KEY,
    SECURE_BROWSER_XSS_FILTER,
    SECURE_CONTENT_TYPE_NOSNIFF,
    SECURE_PROXY_SSL_HEADER,
    SECURE_REFERRER_POLICY,
    SITE_URL,
    STATIC_ROOT,
    STATIC_URL,
    STATIC_VERSION,
    STATICFILES_DIRS,
    STORAGES,
    TEMPLATES,
    TIME_ZONE,
    USE_TZ,
    USE_X_FORWARDED_HOST,
    USE_X_FORWARDED_PORT,
    VAPID_CLAIMS_EMAIL,
    VAPID_PRIVATE_KEY,
    VAPID_PUBLIC_KEY,
    VERSION,
    WINE_AI_SUMMARY_MODEL,
    WSGI_APPLICATION,
    X_FRAME_OPTIONS,
)

# Test-specific settings — use /tmp so Docker containers (non-root user) can write
MEDIA_ROOT = tempfile.mkdtemp(prefix="wine_cellar_test_media_")

# Use simple static files storage in tests (no manifest required)
STORAGES = {  # noqa: F811
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Use dummy cache in tests to prevent cache interference between tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Disable allauth rate limiting in tests (e2e tests trigger many logins)
ACCOUNT_RATE_LIMITS = {}

# Ensure all exports are available
__all__ = [
    "ACCOUNT_ADAPTER",
    "ACCOUNT_RATE_LIMITS",
    "ALLOWED_HOSTS",
    "ANTHROPIC_API_KEY",
    "AUTH_PASSWORD_VALIDATORS",
    "AUTHENTICATION_BACKENDS",
    "BASE_DIR",
    "CACHES",
    "CELLAR_APP_TYPE",
    "CSRF_TRUSTED_ORIGINS",
    "CURRENCIES",
    "CURRENCY_SYMBOLS",
    "DATABASES",
    "DEBUG",
    "DEFAULT_AUTO_FIELD",
    "DEFAULT_WINE_IMAGE",
    "EMAIL_BACKEND",
    "INSTALLED_APPS",
    "LANGUAGE_CODE",
    "LOG_LEVEL",
    "LOGGING",
    "LOGIN_REDIRECT_URL",
    "LOGOUT_REDIRECT_URL",
    "MAP_BASEURL",
    "MEDIA_ROOT",
    "MEDIA_URL",
    "MIDDLEWARE",
    "REST_FRAMEWORK",
    "ROOT_DIR",
    "ROOT_URLCONF",
    "SECRET_KEY",
    "SECURE_BROWSER_XSS_FILTER",
    "SECURE_CONTENT_TYPE_NOSNIFF",
    "SECURE_PROXY_SSL_HEADER",
    "SECURE_REFERRER_POLICY",
    "SITE_URL",
    "STATIC_ROOT",
    "STATIC_URL",
    "STATIC_VERSION",
    "STATICFILES_DIRS",
    "STORAGES",
    "TEMPLATES",
    "TIME_ZONE",
    "USE_TZ",
    "USE_X_FORWARDED_HOST",
    "USE_X_FORWARDED_PORT",
    "VAPID_CLAIMS_EMAIL",
    "VAPID_PRIVATE_KEY",
    "VAPID_PUBLIC_KEY",
    "VERSION",
    "WINE_AI_SUMMARY_MODEL",
    "WSGI_APPLICATION",
    "X_FRAME_OPTIONS",
]
