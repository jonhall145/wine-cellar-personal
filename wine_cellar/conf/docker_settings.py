"""
Docker settings for Wine Cellar.

Imports all base settings and overrides database and cache
configuration to use Docker service containers (PostgreSQL, Redis).
"""

import os

from wine_cellar.conf.settings import (  # noqa: F401
    ACCOUNT_ADAPTER,
    ACCOUNT_RATE_LIMITS,
    ALLOWED_HOSTS,
    ANTHROPIC_API_KEY,
    AUTH_PASSWORD_VALIDATORS,
    AUTHENTICATION_BACKENDS,
    BASE_DIR,
    CELLAR_APP_TYPE,
    CSRF_TRUSTED_ORIGINS,
    CURRENCIES,
    CURRENCY_SYMBOLS,
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

# Database - PostgreSQL via Docker service
DATABASES = {
    "default": {
        "ENGINE": os.environ.get("SQL_ENGINE", "django.db.backends.postgresql"),
        "NAME": os.environ.get("SQL_DATABASE", "django_dev"),
        "USER": os.environ.get("SQL_USER", "django_dev_user"),
        "PASSWORD": os.environ.get("SQL_PASSWORD", "django_dev_password"),
        "HOST": os.environ.get("SQL_HOST", "db"),
        "PORT": os.environ.get("SQL_PORT", "5432"),
    }
}

# Cache - Redis (shared across containers, unlike LocMemCache)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://redis:6379/1"),
        "TIMEOUT": 3600,
    }
}

# Media files - absolute path inside container
MEDIA_ROOT = "/app/media/"
