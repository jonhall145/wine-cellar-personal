"""
Docker production settings for Wine Cellar.

Extends docker_settings with production security headers.
"""

from wine_cellar.conf.docker_settings import *  # noqa: F403, F401

# SSL termination happens at reverse proxy (nginx, cloudflared), not Django
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
