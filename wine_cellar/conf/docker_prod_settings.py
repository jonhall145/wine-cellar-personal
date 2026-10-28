"""
Docker production settings for Wine Cellar.

Extends docker_settings with production security headers and Sentry.
"""

import os

from wine_cellar.conf.docker_settings import (  # noqa: F401
    ACCOUNT_ADAPTER,
    ACCOUNT_RATE_LIMITS,
    ALLOWED_HOSTS,
    ANTHROPIC_API_KEY,
    AUTH_PASSWORD_VALIDATORS,
    AUTHENTICATION_BACKENDS,
    BASE_DIR,
    CACHES,
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
    MEDIA_ROOT,
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

# Sentry error tracking (only if DSN is configured)
_sentry_dsn = os.environ.get("SENTRY_DSN")
if _sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=_sentry_dsn,
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
    )

# JSON structured logging for production
LOGGING["formatters"]["json"] = {  # noqa: F405
    "()": "pythonjsonlogger.json.JsonFormatter",
    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
    "rename_fields": {"asctime": "timestamp", "levelname": "level"},
}
for _handler in LOGGING["handlers"].values():  # noqa: F405
    _handler["formatter"] = "json"

# SSL termination happens at reverse proxy (nginx, cloudflared), not Django
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
