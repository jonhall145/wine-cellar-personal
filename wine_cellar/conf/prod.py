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
