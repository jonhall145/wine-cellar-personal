"""
Docker settings for Wine Cellar.

Imports all base settings and overrides database, cache, and Celery
configuration to use Docker service containers (PostgreSQL, Redis).
"""

import os

from wine_cellar.conf.settings import *  # noqa: F403, F401

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

# Celery - Redis broker via Docker service
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE  # noqa: F405

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
