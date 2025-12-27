import os

import sentry_sdk
from celery.schedules import crontab

from wine_cellar.__init__ import __version__
from wine_cellar.conf.prod import (
    ACCOUNT_ADAPTER,
)
from wine_cellar.conf.prod import ALLOWED_HOSTS as _ALLOWED_HOSTS  # noqa: F401
from wine_cellar.conf.prod import (
    AUTH_PASSWORD_VALIDATORS,
    AUTHENTICATION_BACKENDS,
    BASE_DIR,
    CURRENCIES,
    CURRENCY_SYMBOLS,
)
from wine_cellar.conf.prod import DATABASES as _DATABASES
from wine_cellar.conf.prod import DEBUG as _DEBUG
from wine_cellar.conf.prod import (
    DEFAULT_AUTO_FIELD,
)
from wine_cellar.conf.prod import EMAIL_BACKEND as _EMAIL_BACKEND
from wine_cellar.conf.prod import (
    INSTALLED_APPS,
    LANGUAGE_CODE,
    LANGUAGES,
    LOCALE_PATHS,
    LOGIN_REDIRECT_URL,
    LOGOUT_REDIRECT_URL,
    MAP_BASEURL,
    MEDIA_URL,
    MIDDLEWARE,
    ROOT_DIR,
    ROOT_URLCONF,
)
from wine_cellar.conf.prod import SECRET_KEY as _SECRET_KEY
from wine_cellar.conf.prod import SITE_URL as _SITE_URL
from wine_cellar.conf.prod import STATIC_ROOT as _STATIC_ROOT
from wine_cellar.conf.prod import (
    STATIC_URL,
    STATICFILES_DIRS,
    STORAGES,
    TEMPLATES,
    TIME_ZONE,
    USE_I18N,
    USE_TZ,
    VERSION,
    WSGI_APPLICATION,
)

DEBUG = os.getenv("DJANGO_DEBUG", "False") == "True"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS").split(" ")
SECRET_KEY = os.environ.get("SECRET_KEY")
DATABASES = {
    "default": {
        "ENGINE": os.environ.get("SQL_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.environ.get("SQL_DATABASE", BASE_DIR / "db.sqlite3"),
        "USER": os.environ.get("SQL_USER", "user"),
        "PASSWORD": os.environ.get("SQL_PASSWORD", "password"),
        "HOST": os.environ.get("SQL_HOST", "localhost"),
        "PORT": os.environ.get("SQL_PORT", "5432"),
    }
}

CSRF_TRUSTED_ORIGINS = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS").split(" ")

MEDIA_ROOT = "mediafiles"
STATIC_ROOT = "staticfiles"

SITE_URL = os.environ.get("DJANGO_SITE_URL")

ENABLE_SIGNUPS = os.environ.get("DJANGO_ENABLE_SIGNUPS", False)

EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST")
EMAIL_PORT = os.environ.get("DJANGO_EMAIL_PORT")
EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_USER")
EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_PASSWORD")
# USE_TLS and USE_SSL are mutual exclusive
EMAIL_USE_TLS = os.environ.get("DJANGO_EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = os.environ.get("DJANGO_EMAIL_USE_SSL", "False") == "True"
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL")

if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

CELERY_BROKER_URL = "redis://redis:6379"
CELERY_RESULT_BACKEND = "redis://redis:6379"

CELERY_BEAT_SCHEDULE = {
    "drink_by_reminder": {
        "task": "drink_by_reminder",
        "schedule": crontab(minute="30", hour="2"),
    },
}

SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        release="wine-cellar@" + __version__,
    )
