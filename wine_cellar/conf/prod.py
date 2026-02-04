"""
Production settings for Wine Cellar.

This module imports all base settings and overrides production-specific values.
"""

# Import all base settings explicitly
from wine_cellar.conf.settings import *  # noqa: F403, F401

# Production-specific static file storage uses base settings (gzip-only manifest)

# Production security settings - enforce HTTPS
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Ensure all exports are available
__all__ = [
    "ACCOUNT_ADAPTER",
    "ALLOWED_HOSTS",
    "ANTHROPIC_API_KEY",
    "AUTH_PASSWORD_VALIDATORS",
    "AUTHENTICATION_BACKENDS",
    "BASE_DIR",
    "CSRF_COOKIE_SECURE",
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
    "LANGUAGES",
    "LOCALE_PATHS",
    "LOG_LEVEL",
    "LOGGING",
    "LOGIN_REDIRECT_URL",
    "LOGOUT_REDIRECT_URL",
    "MAP_BASEURL",
    "MEDIA_ROOT",
    "MEDIA_URL",
    "MIDDLEWARE",
    "ROOT_DIR",
    "ROOT_URLCONF",
    "SECRET_KEY",
    "SECURE_BROWSER_XSS_FILTER",
    "SECURE_CONTENT_TYPE_NOSNIFF",
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    "SECURE_HSTS_PRELOAD",
    "SECURE_HSTS_SECONDS",
    "SECURE_REFERRER_POLICY",
    "SECURE_SSL_REDIRECT",
    "SESSION_COOKIE_SECURE",
    "SITE_URL",
    "STATIC_ROOT",
    "STATIC_URL",
    "STATICFILES_DIRS",
    "STORAGES",
    "TEMPLATES",
    "TIME_ZONE",
    "USE_I18N",
    "USE_TZ",
    "VERSION",
    "WSGI_APPLICATION",
    "X_FRAME_OPTIONS",
]
