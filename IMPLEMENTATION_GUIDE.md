# Wine Cellar - Complete Implementation Guide

How to build this project from scratch on a fresh machine. Assumes nothing -- no domain name, no cloud accounts, no existing infrastructure.

---

## Table of Contents

1. [What This Project Is](#1-what-this-project-is)
2. [Prerequisites](#2-prerequisites)
3. [Machine Setup](#3-machine-setup)
4. [Project Scaffolding](#4-project-scaffolding)
5. [Django Project Structure](#5-django-project-structure)
6. [Settings Configuration](#6-settings-configuration)
7. [Database Models](#7-database-models)
8. [URL Routing](#8-url-routing)
9. [Views](#9-views)
10. [Templates](#10-templates)
11. [Frontend Build System](#11-frontend-build-system)
12. [React Components](#12-react-components)
13. [Static Files & WhiteNoise](#13-static-files--whitenoise)
14. [Authentication](#14-authentication)
15. [Celery Background Tasks](#15-celery-background-tasks)
16. [AI Vision Extraction](#16-ai-vision-extraction)
17. [Barcode Scanning](#17-barcode-scanning)
18. [Household Multi-User System](#18-household-multi-user-system)
19. [Hardware Integration (Raspberry Pi)](#19-hardware-integration-raspberry-pi)
20. [Testing](#20-testing)
21. [Linting & Code Quality](#21-linting--code-quality)
22. [Local Development (No Docker)](#22-local-development-no-docker)
23. [Docker Development](#23-docker-development)
24. [Docker Production](#24-docker-production)
25. [Bare-Metal Production](#25-bare-metal-production)
26. [HTTPS & SSL Certificates](#26-https--ssl-certificates)
27. [Backups](#27-backups)
28. [Ongoing Maintenance](#28-ongoing-maintenance)
29. [Hosting on a Local Machine with Cloudflare Tunnel](#29-hosting-on-a-local-machine-with-cloudflare-tunnel)
30. [Hosting: LAN-Only Access (No Internet Exposure)](#30-hosting-lan-only-access-no-internet-exposure)
31. [Hosting: VPN/Meshnet Access](#31-hosting-vpnmeshnet-access)
32. [Hosting: Reverse Proxy with Nginx or Caddy](#32-hosting-reverse-proxy-with-nginx-or-caddy)
33. [Hosting: Choosing Your Hardware](#33-hosting-choosing-your-hardware)
34. [Hosting: Systemd Auto-Start on Boot](#34-hosting-systemd-auto-start-on-boot)
35. [Hosting: Firewall Configuration](#35-hosting-firewall-configuration)
36. [Hosting: Monitoring & Health Checks](#36-hosting-monitoring--health-checks)
37. [Putting It All Together: Complete Raspberry Pi Deployment](#37-putting-it-all-together-complete-raspberry-pi-deployment)

---

## 1. What This Project Is

A self-hosted web application for managing a personal wine collection. Users can:

- Track wines with detailed metadata (name, vintage, country, type, grapes, ABV, price)
- Manage physical storage locations with grid-based layouts
- Scan barcodes to quickly add or find wines
- Photograph wine labels and extract data using AI (Claude API)
- View wine origins on an interactive map
- Track consumption history and tasting notes
- Set drinking window alerts and reorder reminders
- Share a cellar with household members (role-based access)
- Optionally integrate a Raspberry Pi for vision-based rack monitoring

**Tech stack:** Django 5.2, React 19, TypeScript, Webpack 5, PostgreSQL (prod) / SQLite (dev), Redis, Celery, PureCSS, Leaflet maps.

---

## 2. Prerequisites

### Hardware

Any machine that can run Python 3.12+ and Node.js 20+. This project runs on everything from a Raspberry Pi 4 to a cloud VM. 2GB RAM minimum, 4GB recommended.

### Software to Install

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.12+ | Backend runtime |
| Node.js | 20+ | Frontend build toolchain |
| npm | 10+ | JavaScript package manager |
| Git | 2.x | Version control |
| SQLite | 3.x | Default development database (usually pre-installed) |
| libzbar0 | any | Barcode reading (pyzbar dependency) |
| OpenSSL | any | SSL certificate generation |

For production, you will also need:

| Software | Version | Purpose |
|----------|---------|---------|
| PostgreSQL | 16 | Production database |
| Redis | 7 | Cache + Celery message broker |

Or use Docker to run PostgreSQL and Redis in containers.

### Optional

| Software | Purpose |
|----------|---------|
| Docker + Docker Compose | Containerized deployment |
| Anthropic API key | AI wine label extraction (Claude) |

---

## 3. Machine Setup

### Ubuntu/Debian

```bash
# System packages
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip \
    nodejs npm git sqlite3 libzbar0 openssl curl

# For production (if not using Docker)
sudo apt install -y postgresql-16 redis-server libpq-dev

# Verify versions
python3 --version   # 3.12+
node --version      # v20+
npm --version       # 10+
```

### macOS

```bash
brew install python@3.11 node@20 git sqlite zbar openssl

# For production (if not using Docker)
brew install postgresql@16 redis
```

### Raspberry Pi OS (Bookworm)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip \
    nodejs npm git sqlite3 libzbar0 openssl curl libpq-dev

# Node.js 20 may need to be installed via NodeSource if the default is older:
# curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
# sudo apt install -y nodejs
```

---

## 4. Project Scaffolding

### Initialize the Repository

```bash
mkdir wine-cellar && cd wine-cellar
git init
```

### Create the Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### Create the Django Project

```bash
pip install Django==5.2.9
django-admin startproject wine_cellar .

# Move settings into a conf/ directory
mkdir -p wine_cellar/conf
mv wine_cellar/settings.py wine_cellar/conf/settings.py
mv wine_cellar/urls.py wine_cellar/conf/urls.py
mv wine_cellar/wsgi.py wine_cellar/conf/wsgi.py
mv wine_cellar/asgi.py wine_cellar/conf/asgi.py
```

Update `manage.py` to point to the new settings location:
```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wine_cellar.conf.settings")
```

And in `wine_cellar/conf/wsgi.py`:
```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wine_cellar.conf.settings")
```

### Create Django Apps

```bash
mkdir -p wine_cellar/apps
cd wine_cellar/apps

python ../../manage.py startapp wine
python ../../manage.py startapp storage
python ../../manage.py startapp user
python ../../manage.py startapp household
python ../../manage.py startapp hardware

cd ../..
```

### Initialize npm

```bash
npm init -y
```

### Directory Structure to Create

```bash
mkdir -p wine_cellar/templates/includes
mkdir -p wine_cellar/templates/allauth
mkdir -p wine_cellar/templates/household
mkdir -p wine_cellar/assets/{css,js,images}
mkdir -p wine_cellar/react/components
mkdir -p wine_cellar/react/maps
mkdir -p wine_cellar/static
mkdir -p tests/{user,storage}
mkdir -p fixtures
mkdir -p requirements
mkdir -p docs
mkdir -p media
mkdir -p ssl
```

---

## 5. Django Project Structure

The final structure should look like this:

```
wine_cellar/
  __init__.py          # Exports celery_app and __version__
  middleware.py        # CacheControlMiddleware
  storage.py           # GzipOnlyManifestStaticFilesStorage
  conf/
    __init__.py
    settings.py        # Base settings
    test.py            # Test settings
    prod.py            # Production settings
    docker_settings.py # Docker development settings
    docker_prod_settings.py
    celery.py          # Celery app configuration
    urls.py            # Root URL configuration
    wsgi.py            # WSGI application
    asgi.py            # ASGI application
  apps/
    wine/              # Core wine management
    storage/           # Inventory & physical locations
    user/              # User preferences
    household/         # Multi-user households
    hardware/          # Raspberry Pi integration
  templates/           # Django HTML templates
  assets/              # Source CSS/JS/images (pre-build)
  react/               # React/TypeScript components
  static/              # Webpack build output (generated)
```

### `wine_cellar/__init__.py`

```python
from .conf.celery import celery_app

__all__ = ("celery_app",)
__version__ = "0.3.0"
```

---

## 6. Settings Configuration

### Base Settings (`wine_cellar/conf/settings.py`)

This is the core settings file. Key decisions:

```python
import os
from pathlib import Path
from django.utils.translation import gettext_lazy as _
from wine_cellar import __version__

# Path setup - ROOT_DIR is project root, BASE_DIR is wine_cellar/
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BASE_DIR = Path(__file__).resolve().parent.parent
VERSION = __version__

# Security - secret key from environment, default only for development
SECRET_KEY = os.environ.get(
    "SECRET_KEY", "django-insecure-dev-only-key-do-not-use-in-production"
)

# Debug defaults to False for safety
DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"

# Hosts and CSRF from environment
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CSRF_TRUSTED_ORIGINS = os.environ.get(
    "DJANGO_CSRF_TRUSTED_ORIGINS", "http://127.0.0.1:8000"
).split(",")

# Anthropic API key for AI features
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_celery_beat",          # Scheduled tasks UI in admin
    "django_extensions",           # runserver_plus for HTTPS dev
    "allauth",                     # Authentication framework
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.openid_connect",
    "widget_tweaks",               # Template form field rendering
    "wine_cellar.apps.household",
    "wine_cellar.apps.wine",
    "wine_cellar.apps.user",
    "wine_cellar.apps.storage",
    "wine_cellar.apps.hardware",
]

MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.http.ConditionalGetMiddleware",
    "wine_cellar.middleware.CacheControlMiddleware",       # Custom: private, no-store
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",           # Static file serving
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",  # All views require login
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "wine_cellar.apps.household.middleware.HouseholdMiddleware",
]

ROOT_URLCONF = "wine_cellar.conf.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "wine_cellar.apps.household.context_processors.household_context",
            ],
        },
    },
]

WSGI_APPLICATION = "wine_cellar.conf.wsgi.application"

# Default database: SQLite for development
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "db.sqlite3",
        "TEST": {"NAME": "test_db.sqlite3"},
    }
}

# Cache: in-memory for development
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "wine-cellar-cache",
        "TIMEOUT": 3600,
        "OPTIONS": {"MAX_ENTRIES": 1000},
    }
}

# Authentication backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Password validators - all four standard Django validators
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Europe/Berlin"
USE_I18N = False
USE_TZ = True
LANGUAGES = [("en-gb", _("British English"))]

# Currencies
CURRENCIES = [("EUR", _("Euro")), ("USD", _("Dollar")), ("GBP", _("Pound Sterling"))]
CURRENCY_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£"}

# Static files
STATIC_URL = "/static/"
STATIC_VERSION = VERSION
STATIC_ROOT = ROOT_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Custom storage: gzip-only compression (no brotli, faster collectstatic)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "wine_cellar.storage.GzipOnlyManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Media files
MEDIA_ROOT = "media/"
MEDIA_URL = "media/"
DEFAULT_WINE_IMAGE = "images/bottle.svg"

# Map tiles
MAP_BASEURL = "https://tiles.openfreemap.org/styles/positron"

# Email - console output in development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:8000")

# Allauth adapter
ACCOUNT_ADAPTER = "wine_cellar.apps.user.signup_adapter.ConfigurableSignupAccountAdapter"

# Rate limiting
ACCOUNT_RATE_LIMITS = {
    "login": "5/m/ip",
    "login_failed": "5/m/ip,10/h/ip",
    "signup": "5/m/ip",
    "password_reset": "5/m/ip",
}

# Security headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
```

### Test Settings (`wine_cellar/conf/test.py`)

```python
from wine_cellar.conf.settings import *  # noqa

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

CELERY_TASK_ALWAYS_EAGER = True
```

### Production Settings (`wine_cellar/conf/prod.py`)

```python
from wine_cellar.conf.settings import *  # noqa

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

### Docker Settings (`wine_cellar/conf/docker_settings.py`)

```python
import os
from wine_cellar.conf.settings import *  # noqa

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

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE  # noqa

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://redis:6379/1"),
        "TIMEOUT": 3600,
        "OPTIONS": {"MAX_ENTRIES": 1000},
    }
}

MEDIA_ROOT = "/app/media/"
```

### Celery Configuration (`wine_cellar/conf/celery.py`)

```python
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wine_cellar.conf.settings")

celery_app = Celery()
celery_app.config_from_object("django.conf:settings", namespace="CELERY")
celery_app.autodiscover_tasks()
```

---

## 7. Database Models

### Abstract Base: `UserContentModel`

All user-owned content inherits from this. It provides ownership (user + household), created/modified timestamps.

```python
# wine_cellar/apps/wine/models.py

class UserContentModel(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, null=True)
    household = models.ForeignKey(
        "household.Household", on_delete=models.CASCADE,
        null=True, blank=True, related_name="%(class)s_items",
    )
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
```

### Wine App Models

**Wine** -- the core model. Fields:
- `name` (CharField 100)
- `wine_type` (CharField 2, choices: WH/RE/RO/SP/DE/FO/OR for White/Red/Rose/Sparkling/Dessert/Fortified/Orange)
- `category` (CharField 2, nullable, choices: DR/SD/MS/SW/FH for Dry/Semi-Dry/Medium Sweet/Sweet/Feinherb)
- `vintage` (PositiveIntegerField, nullable, indexed, min 1900)
- `country` (CharField 3, pycountry choices, indexed)
- `subregion` (CharField 100, nullable)
- `appellation` (FK to Appellation, nullable)
- `abv` (FloatField, nullable)
- `size` (FK to Size, nullable)
- `price` (DecimalField 6,2, nullable)
- `rrp` (DecimalField 6,2, nullable)
- `price_url` (URLField 500, nullable)
- `drink_by` (DateField, nullable, indexed)
- `drink_from` (PositiveIntegerField, nullable -- year)
- `drink_to` (PositiveIntegerField, nullable, indexed -- year)
- `comment` (CharField 250, blank)
- `rating` (PositiveIntegerField 0-3, nullable)
- `grapes` (M2M to Grape)
- `vineyard` (M2M to Vineyard)
- `source` (M2M to Source)
- `food_pairings` (M2M to FoodPairing)
- `attributes` (M2M to Attribute)

Unique constraint: `(name, wine_type, abv, size, vintage, country, user)`.

**Supporting models:**
- `Grape` -- name + user (unique per user)
- `Vineyard` -- name, website, region, country + user
- `FoodPairing` -- name + user
- `Attribute` -- name + user (tasting descriptors like "oaky", "fruity")
- `Size` -- choices: Piccolo/Demi/Half/Standard/Liter/Magnum/Jeroboam/Rehoboam
- `Source` -- name, url, price_selector (for price scraping)
- `Appellation` -- name, country, latitude, longitude, parent_region (self-FK)

**Image models:**
- `WineImage` -- image (ImageField), thumbnail, wine (FK), user, image_type (Label Front/Back), is_primary
- `WineBarcode` -- wine (FK), barcode (CharField), user, household

**Activity models:**
- `DrinkRecord` -- wine, date_consumed, tasting_notes, rating, shared_with, occasion, storage_item
- `BottleNote` -- storage_item (FK), note_date, note text
- `Wishlist` -- name, wine_type, country, vintage, price_limit, notes, priority, purchased

**Alert models:**
- `DrinkingWindowAlert` -- wine, alert_date, message, is_read
- `ReorderReminder` -- wine, min_stock, is_active
- `SaleAlert` -- wine, source, threshold_percent, threshold_price, is_active, last_notified

**Analytics models:**
- `VisionExtractionLog` -- image_count, raw_response, extracted_data (JSON), confidence, wine, processing_time_ms
- `PriceHistory` -- wine, source, price, recorded_at

### Storage App Models

**Storage** -- physical storage locations:
- `name` (CharField 100)
- `description` (TextField, nullable)
- `location` (CharField 100)
- `rows` (PositiveIntegerField, default 0)
- `columns` (PositiveIntegerField, default 0)
- `is_cold` (BooleanField)
- `order` (PositiveIntegerField, display ordering)
- `is_default` (BooleanField, only one per user)
- Properties: `total_slots`, `used_slots`, `is_full`, `get_free_cells_by_row`

**StorageItem** -- individual bottles in storage:
- `storage` (FK to Storage)
- `wine` (FK to Wine)
- `row`, `column` (PositiveIntegerField, nullable)
- `deleted` (BooleanField, indexed -- soft deletion)
- `price` (DecimalField 6,2, nullable)
- `is_gift` (BooleanField)
- `gift_from`, `occasion` (CharField, nullable)
- `rating` (PositiveIntegerField 0-3, nullable)

Indexes: `(user, deleted)`, `(storage, row, column)`, `(wine, deleted)`.

### User App Models

**UserSettings** -- per-user preferences:
- `user` (OneToOneField)
- `active_household` (FK to Household, nullable)
- `language`, `currency`, `notifications`

### Household App Models

**Household** -- shared wine cellars:
- `name` (CharField 100)
- `created`, `modified`

**HouseholdMembership** -- user roles:
- `user`, `household` (unique together)
- `role` (Viewer/Member/Admin/Owner with hierarchy 0/1/2/3)
- `joined`, `invited_by`

**HouseholdInvitation** -- invite tokens:
- `household`, `email`, `role`
- `token` (unique, 48-byte urlsafe random)
- `status` (Pending/Accepted/Declined/Expired)
- `expires` (7 days from creation)
- Methods: `is_valid()`, `accept(user)`, `decline()`

**HouseholdSettings** -- household-level preferences (language, currency, notifications).

### Hardware App Models

For Raspberry Pi rack monitoring:

- **PositionChangeReview** -- detected bottle adds/removes needing user confirmation
- **RackSnapshot** -- periodic photos of the rack
- **HardwareDevice** -- registered Pi devices (device_id, api_token, firmware_version)
- **OfflineOperation** -- queued operations from offline periods
- **RackVisionConfig** -- vision system settings (auto_apply_threshold, calibration_data)

### Creating Migrations

After defining all models:

```bash
python manage.py makemigrations wine storage user household hardware
python manage.py migrate
```

---

## 8. URL Routing

The root URL configuration (`wine_cellar/conf/urls.py`) maps every endpoint. The project does NOT use a REST API framework -- views serve HTML templates with some AJAX endpoints returning JSON.

Key URL patterns:

```python
urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Authentication (django-allauth)
    path("accounts/", include("allauth.urls")),

    # Household management
    path("household/", include("wine_cellar.apps.household.urls")),

    # Hardware API (Raspberry Pi)
    path("api/v1/", include("wine_cellar.apps.hardware.urls", namespace="hardware-api")),
    path("hardware/", include(("wine_cellar.apps.hardware.web_urls", "hardware"), namespace="hardware")),

    # User settings
    path("user/settings/", UserSettingsView.as_view(), name="user-settings"),

    # Storage CRUD
    path("storages/", StorageListView.as_view(), name="storage-list"),
    path("storage/<int:pk>/", StorageDetailView.as_view(), name="storage-detail"),
    path("storage/add/", StorageCreateView.as_view(), name="storage-add"),
    path("storage/edit/<int:pk>/", StorageUpdateView.as_view(), name="storage-edit"),
    path("storage/delete/<int:pk>/", StorageDeleteView.as_view(), name="storage-delete"),
    path("storage/move-up/<int:pk>/", storage_move_up, name="storage-move-up"),
    path("storage/move-down/<int:pk>/", storage_move_down, name="storage-move-down"),
    path("storage/history/", StorageItemHistoryView.as_view(), name="storage-history"),

    # Storage API (React grid)
    path("api/storage/grid-data/", storage_grid_data, name="storage-grid-data"),
    path("api/storage/move-bottle/", move_bottle, name="storage-move-bottle"),

    # Bottles (StorageItem)
    path("stock/add/<int:pk>/", StorageItemAddView.as_view(), name="stock-add"),
    path("stock/delete/<int:pk>/", StorageItemDeleteView.as_view(), name="stock-delete"),
    path("bottles/", StorageItemListView.as_view(), name="bottle-list"),
    path("bottle/edit/<int:pk>/", StorageItemUpdateView.as_view(), name="bottle-edit"),
    path("bottle/<int:pk>/note/", BottleNoteCreateView.as_view(), name="bottle-note-add"),

    # Wine CRUD
    path("wines/", WineListView.as_view(), name="wine-list"),
    path("wine/add/", WineCreateView.as_view(), name="wine-add"),
    path("wine/add/<str:code>/", WineCreateView.as_view(), name="wine-add"),
    path("wine/<int:pk>/", WineDetailView.as_view(), name="wine-detail"),
    path("wine/<int:pk>/images/", WineImagesView.as_view(), name="wine-images"),
    path("wine/edit/<int:pk>/", WineUpdateView.as_view(), name="wine-edit"),
    path("wine/delete/<int:pk>/", WineDeleteView.as_view(), name="wine-delete"),

    # Wine scanning
    path("wine/scan/", WineScanView.as_view(), name="wine-scan"),
    path("wine/scan/<str:code>/", WineScannedView.as_view(), name="wine-scan"),
    path("wine/scan-barcode/", scan_barcode_ajax, name="wine-scan-barcode"),
    path("wine/extract-vision/", extract_wine_vision_ajax, name="wine-extract-vision"),
    path("label-scan/", LabelScanView.as_view(), name="label-scan"),

    # Wine images
    path("wine/image/<int:pk>/set-primary/", set_primary_image, name="set-primary-image"),
    path("wine/image/<int:pk>/crop/", crop_wine_image, name="crop-wine-image"),

    # Consumption
    path("wine/<int:pk>/drink/", DrinkRecordCreateView.as_view(), name="drink-record-add"),
    path("drink-history/", DrinkRecordListView.as_view(), name="drink-history"),
    path("drink-history/edit/<int:pk>/", DrinkRecordEditView.as_view(), name="drink-record-edit"),
    path("drink-history/delete/<int:pk>/", DrinkRecordDeleteView.as_view(), name="drink-record-delete"),

    # Map
    path("wines/map/", WineMapView.as_view(), name="wine-map"),

    # Wishlist
    path("wishlist/", WishlistListView.as_view(), name="wishlist-list"),
    path("wishlist/add/", WishlistCreateView.as_view(), name="wishlist-add"),
    path("wishlist/delete/<int:pk>/", WishlistDeleteView.as_view(), name="wishlist-delete"),
    path("wishlist/purchased/<int:pk>/", WishlistPurchasedView.as_view(), name="wishlist-purchased"),

    # Analytics
    path("cellar-value/", CellarValueView.as_view(), name="cellar-value"),
    path("stats/", ConsumptionStatsView.as_view(), name="consumption-stats"),
    path("alerts/", DrinkingWindowAlertsView.as_view(), name="drinking-alerts"),

    # Reminders & alerts
    path("reorder/", ReorderRemindersView.as_view(), name="reorder-reminders"),
    path("reorder/add/<int:pk>/", ReorderReminderCreateView.as_view(), name="reorder-reminder-add"),
    path("reorder/delete/<int:pk>/", ReorderReminderDeleteView.as_view(), name="reorder-reminder-delete"),
    path("sale-alerts/", SaleAlertsView.as_view(), name="sale-alerts"),
    path("sale-alerts/add/", SaleAlertCreateView.as_view(), name="sale-alert-add"),
    path("sale-alerts/delete/<int:pk>/", SaleAlertDeleteView.as_view(), name="sale-alert-delete"),
    path("sale-alerts/toggle/<int:pk>/", SaleAlertToggleView.as_view(), name="sale-alert-toggle"),

    # Utility
    path("health/", health_check, name="health_check"),
    path("", HomePageView.as_view(), name="homepage"),
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
]

# Media file serving with cache headers
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve_media),
]
```

The `serve_media` function is a custom view that adds `Cache-Control` and `Last-Modified` headers to media file responses, with `If-Modified-Since` support for 304 responses.

---

## 9. Views

Views use Django's class-based views (ListView, DetailView, CreateView, UpdateView, DeleteView). Key patterns:

- All views filter by `user=request.user` (or by household if in household mode)
- AJAX endpoints return JSON for React components
- The `@login_not_required` decorator is used for the health check and media serving

The views are standard Django CBVs -- nothing exotic. Example structure:

```python
class WineListView(ListView):
    model = Wine
    template_name = "wine/wine_list.html"
    paginate_by = 20

    def get_queryset(self):
        return Wine.objects.filter(user=self.request.user)
```

---

## 10. Templates

### Base Template

Uses PureCSS as the CSS framework (loaded from CDN). Structure:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <!-- PureCSS from CDN -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/purecss@3.0.0/build/pure-min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/purecss@3.0.0/build/grids-responsive-min.css">

    <!-- App CSS (webpack-built) -->
    <link rel="stylesheet" href="{% static 'base.css' %}?v={% get_setting 'VERSION' %}">

    {% block styles %}{% endblock %}
    {% block extra_js %}{% endblock %}
</head>
<body class="layout">
    <header>
        <!-- Mobile hamburger menu -->
        <!-- Desktop horizontal menu -->
    </header>

    <main class="main">
        {% block content %}{% endblock %}
    </main>

    <!-- Mobile bottom navigation (Home, Wines, Add, Scan, Storage) -->
    <nav class="bottom-nav">...</nav>

    <footer>AGPL 3.0 | Version</footer>

    <script src="{% static 'base.js' %}?v={% get_setting 'VERSION' %}" defer></script>
</body>
</html>
```

### Mobile-First Design

The app is mobile-first. Bottom navigation for mobile, horizontal menu for desktop. PureCSS grid system handles responsiveness. Touch targets must be minimum 44px.

### FontAwesome Icons

FontAwesome 7.1.0 is bundled through webpack (not CDN). Icons are used for navigation and buttons.

---

## 11. Frontend Build System

### Webpack Setup

Three webpack config files:

**`webpack.common.js`** -- shared configuration:
- Entry points for each page/feature (base CSS/JS, barcode scanner, label scanner, maps, storage grid, etc.)
- Loaders: Babel (JS/JSX), ts-loader (TypeScript), CSS/SCSS, fonts, images
- Plugins: MiniCssExtractPlugin, CopyWebpackPlugin
- Output to `wine_cellar/static/`

**`webpack.dev.js`** -- development additions:
```javascript
const { merge } = require('webpack-merge')
const common = require('./webpack.common.js')

module.exports = merge(common, {
  devtool: 'eval-cheap-module-source-map'
})
```

**`webpack.prod.js`** -- production additions:
```javascript
const { merge } = require('webpack-merge')
const common = require('./webpack.common.js')
const TerserPlugin = require('terser-webpack-plugin')

module.exports = merge(common, {
  devtool: false,
  optimization: {
    minimize: true,
    minimizer: [new TerserPlugin({ parallel: true, extractComments: false })]
  }
})
```

### npm Dependencies

Install these:

```bash
# Runtime dependencies
npm install react react-dom leaflet react-leaflet leaflet.markercluster \
    @maplibre/maplibre-gl-leaflet tom-select barcode-detector react-barcode-scanner \
    @dnd-kit/core @dnd-kit/utilities @babel/runtime \
    @fortawesome/fontawesome-free @fortawesome/fontawesome-svg-core \
    @fortawesome/free-solid-svg-icons

# Dev dependencies
npm install --save-dev webpack webpack-cli webpack-merge \
    @babel/core @babel/preset-env @babel/preset-react \
    @babel/plugin-transform-runtime @babel/plugin-transform-modules-commonjs \
    babel-loader ts-loader typescript \
    css-loader sass sass-loader postcss postcss-loader autoprefixer \
    mini-css-extract-plugin copy-webpack-plugin \
    @types/react @types/react-dom \
    eslint prettier eslint-config-prettier neostandard \
    husky lint-staged path-browserify url
```

### npm Scripts (`package.json`)

```json
{
  "scripts": {
    "build": "webpack --config webpack.dev.js --mode development",
    "build:prod": "webpack --config webpack.prod.js --mode production",
    "watch": "webpack --config webpack.dev.js --watch --mode development",
    "lint": "eslint wine_cellar/assets",
    "lint-fix": "eslint --fix wine_cellar",
    "prepare": "husky"
  }
}
```

### TypeScript Configuration (`tsconfig.json`)

```json
{
  "compilerOptions": {
    "target": "es2016",
    "module": "esnext",
    "moduleResolution": "bundler",
    "jsx": "react",
    "strict": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true,
    "incremental": true
  }
}
```

---

## 12. React Components

React is used for interactive features only -- not for the whole app. Each component is mounted into a specific `<div>` rendered by Django templates.

### Barcode Scanner (`wine_cellar/react/react_bar_code.tsx`)

- Uses `react-barcode-scanner` and the browser's Barcode Detection API
- Shows camera feed, detects barcodes (EAN-13, UPC-A)
- On detection: AJAX POST to `/wine/scan-barcode/` with the barcode value
- Server stores barcode in session and redirects to wine create/detail

### Label Scanner (`wine_cellar/react/react_label_scanner.tsx`)

- Captures wine label photos from camera
- Stores base64 images in session
- AJAX POST to `/wine/extract-vision/` to send images to Claude API
- Returns extracted wine data to auto-fill the create form

### Storage Grid (`wine_cellar/react/storage_grid.tsx`)

- Renders storage as a grid (rows x columns)
- Drag-and-drop bottle repositioning using `@dnd-kit`
- AJAX calls to `/api/storage/move-bottle/` for position updates

### Maps (`wine_cellar/react/maps/react_maps.tsx`)

- Leaflet map with OpenFreeMap tiles (positron style)
- Wine origin countries shown as markers
- MarkerCluster for grouping
- Country boundary GeoJSON overlays

Each React component is bundled as a separate webpack entry point and loaded only on pages that need it.

---

## 13. Static Files & WhiteNoise

### How It Works

1. Webpack builds frontend assets into `wine_cellar/static/`
2. `python manage.py collectstatic` gathers everything into `staticfiles/` with a manifest
3. WhiteNoise serves these files directly from the Django process in production
4. A custom `GzipOnlyManifestStaticFilesStorage` compresses files with gzip only (skips brotli for faster builds)

### Custom Storage Backend (`wine_cellar/storage.py`)

```python
from whitenoise.compress import Compressor
from whitenoise.storage import CompressedManifestStaticFilesStorage

class GzipOnlyManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    def create_compressor(self, **kwargs):
        kwargs["use_brotli"] = False
        return Compressor(**kwargs)
```

### Custom Middleware (`wine_cellar/middleware.py`)

```python
class CacheControlMiddleware:
    """Set Cache-Control: private, no-store on page responses."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.has_header("Cache-Control"):
            return response
        if request.path.startswith("/static/") or request.path.startswith("/media/"):
            return response
        response["Cache-Control"] = "private, no-store"
        return response
```

---

## 14. Authentication

### django-allauth Setup

The project uses `django-allauth` for authentication. It provides:

- Local username/password authentication
- OpenID Connect support (for SSO if desired)
- Rate limiting on login/signup/password-reset
- Customizable signup adapter

### Key Decisions

- `LoginRequiredMiddleware` in the middleware stack means ALL views require login by default
- Public views (health check, media serving) use `@login_not_required`
- Rate limiting: 5 attempts per minute per IP on login, signup, and password reset
- Custom adapter controls whether new user signup is allowed

### Templates

Allauth templates are overridden in `wine_cellar/templates/allauth/` for consistent styling with the rest of the app.

---

## 15. Celery Background Tasks

### What Celery Does

- **Drink-by reminders**: Email users when wines approach their drinking window
- **Reorder notifications**: Alert when stock drops below threshold
- **Image processing**: Generate thumbnails asynchronously

### Setup

1. Install Celery and django-celery-beat:
   ```
   celery==5.6.1
   django-celery-beat==2.8.1
   ```

2. Configure the Celery app (`wine_cellar/conf/celery.py`)

3. Import it in `wine_cellar/__init__.py`:
   ```python
   from .conf.celery import celery_app
   __all__ = ("celery_app",)
   ```

4. Add `"django_celery_beat"` to `INSTALLED_APPS`

5. Configure broker (Redis):
   ```python
   CELERY_BROKER_URL = "redis://redis:6379/0"
   CELERY_RESULT_BACKEND = "redis://redis:6379/0"
   ```

6. Run the worker and beat scheduler:
   ```bash
   celery -A wine_cellar.conf.celery:celery_app worker --loglevel=info
   celery -A wine_cellar.conf.celery:celery_app beat --loglevel=info \
       --scheduler django_celery_beat.schedulers:DatabaseScheduler
   ```

### Test Mode

In test settings, `CELERY_TASK_ALWAYS_EAGER = True` makes tasks execute synchronously.

---

## 16. AI Vision Extraction

### How It Works

1. User takes a photo of a wine label (via the React label scanner component)
2. Image is sent as base64 to `/wine/extract-vision/` endpoint
3. Server sends image to the Anthropic API (Claude Haiku 4.5) with a structured prompt
4. Claude extracts: wine name, vintage, country, grape variety, ABV, type, etc.
5. Extracted data is returned as JSON to auto-fill the wine create form
6. Each extraction is logged in `VisionExtractionLog` for analysis

### Requirements

- Anthropic API key set in `ANTHROPIC_API_KEY` environment variable
- `anthropic==0.40.0` Python package
- Images are resized to max 1568px before sending to the API

### Without the API Key

The feature gracefully degrades -- the label scanner UI still works, but the AI extraction won't run. Users can still manually fill in the form.

---

## 17. Barcode Scanning

### Two Methods

1. **Browser Barcode Detection API** (hardware-accelerated, built into modern browsers)
2. **pyzbar** (software-based, server-side from uploaded images)

### System Dependency

```bash
# Required for pyzbar
sudo apt install libzbar0
```

### Flow

1. React barcode scanner component accesses camera
2. Barcode detected in browser -> AJAX POST to `/wine/scan-barcode/`
3. Server checks if barcode matches existing wine (via WineBarcode model)
4. If found: redirect to wine detail
5. If not found: redirect to wine create form with barcode pre-filled

### HTTPS Requirement

Mobile browsers require HTTPS to access the camera. Use `./run_https.sh` for development or ensure HTTPS in production.

---

## 18. Household Multi-User System

### How It Works

1. A user creates a household and becomes the Owner
2. Owner/Admin can invite other users via email (generates a token link)
3. Invited user accepts the invitation and joins with the assigned role
4. Users set their "active household" in user settings
5. All data queries filter by the active household
6. `HouseholdMiddleware` sets the household context on every request

### Role Hierarchy

| Role | Level | Can Do |
|------|-------|--------|
| Viewer | 0 | Read data |
| Member | 1 | Create/read/update/delete data |
| Admin | 2 | + manage members |
| Owner | 3 | + delete household |

### Invitation Flow

1. Admin creates invitation (email, role) -> generates secure 48-byte token
2. Invitation expires after 7 days
3. Recipient clicks link with token -> accepts/declines
4. On accept: `HouseholdMembership` created automatically

---

## 19. Hardware Integration (Raspberry Pi)

### Architecture

A Raspberry Pi with a camera monitors a wine rack:

1. Pi takes periodic snapshots and uses vision to detect bottle positions
2. Position changes (additions/removals) are sent to the Django API
3. Changes with high confidence are auto-applied; others need user review
4. Pi can operate offline and sync when connectivity is restored

### API Endpoints

The hardware app exposes REST-like API endpoints under `/api/v1/` for the Pi client:
- Device registration and heartbeat
- Position change reporting
- Snapshot uploads
- Offline operation sync
- Configuration retrieval

### Authentication

Pi devices authenticate using API tokens stored in the `HardwareDevice` model.

---

## 20. Testing

### Framework

- **pytest** with `pytest-django` for Django integration
- **factory-boy** with `pytest-factoryboy` for test data
- **pytest-cov** for coverage

### Configuration (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "wine_cellar.conf.test"
python_files = ["test_*.py", "*_test.py"]

[tool.coverage.run]
omit = ["wine_cellar/conf/*", "**/tests/*", "**/migrations/*"]

[tool.coverage.report]
fail_under = 80
show_missing = true
```

### Test Factories (`tests/conftest.py`)

Create factories for all models using `factory-boy`:

```python
import factory
from wine_cellar.apps.wine.models import Wine

class WineFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Wine

    name = factory.Faker("word")
    wine_type = "RE"
    country = "FR"
    vintage = 2020
    user = factory.SubFactory(UserFactory)
```

### Running Tests

```bash
# All tests
venv/bin/py.test --reuse-db

# With coverage
venv/bin/py.test --reuse-db --cov --cov-report=html

# Only failed tests
venv/bin/py.test --reuse-db --last-failed

# Clean database
rm test_db.sqlite3 && venv/bin/py.test
```

---

## 21. Linting & Code Quality

### Python Linting

- **black** -- code formatting (line length 88)
- **isort** -- import sorting (profile: black)
- **flake8** -- style checking (excludes migrations and settings)

### JavaScript/TypeScript Linting

- **eslint** with prettier and neostandard
- **stylelint** for CSS/SCSS

### Template Linting

- **djlint** for Django templates (ignores H030, H031, T002)

### Pre-commit Hooks

Install with:
```bash
pip install pre-commit
pre-commit install
```

Hooks run automatically on every commit: trailing whitespace, end-of-file fixer, black, isort, flake8, djlint.

### Makefile Lint Target

```bash
make lint   # Runs isort, flake8, npm lint, makemigrations --check
```

---

## 22. Local Development (No Docker)

The simplest way to run the project.

### Step-by-Step

```bash
# 1. Clone the repository
git clone <repo-url>
cd wine-cellar

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements/dev.txt

# 4. Install Node dependencies and build frontend
npm install --no-save
npm run build

# 5. Create environment file
cp .env.dev-sample .env.dev
# Edit .env.dev with your settings (at minimum, set ADMIN_USER_PASSWORD)

# 6. Run migrations
python manage.py migrate

# 7. Load sample data (optional)
python manage.py loaddata fixtures/user.json
python manage.py loaddata fixtures/grapes.json
python manage.py loaddata fixtures/appellations.json
python manage.py loaddata fixtures/wines.json
python manage.py loaddata fixtures/stock.json

# 8. Start the development server
./run_local.sh
# Or simply:
DJANGO_DEBUG=True python manage.py runserver 8003
```

Access at http://127.0.0.1:8003

### With Frontend Watch Mode

```bash
make watch
# This runs both npm watch AND the Django dev server
```

### Environment File (`.env.dev`)

```bash
DJANGO_DEBUG=True
SECRET_KEY=any-random-string-for-dev
DJANGO_ALLOWED_HOSTS=0.0.0.0,localhost,127.0.0.1,[::1]
DJANGO_CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8003
DJANGO_SETTINGS_MODULE=wine_cellar.conf.settings
ADMIN_USER=admin
ADMIN_USER_EMAIL=admin@example.org
ADMIN_USER_PASSWORD=your-dev-password
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here  # Optional
```

---

## 23. Docker Development

Uses PostgreSQL, Redis, and Celery in containers.

### Files Needed

**`.env.docker`:**
```bash
DJANGO_DEBUG=True
DJANGO_SETTINGS_MODULE=wine_cellar.conf.docker_settings
SECRET_KEY=docker-dev-insecure-key-do-not-use-in-production
DJANGO_ALLOWED_HOSTS=0.0.0.0,localhost,127.0.0.1,[::1]
DJANGO_CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8003,http://localhost:8003
SQL_ENGINE=django.db.backends.postgresql
SQL_DATABASE=django_dev
SQL_USER=django_dev_user
SQL_PASSWORD=django_dev_password
SQL_HOST=db
SQL_PORT=5432
DATABASE=postgres
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
REDIS_URL=redis://redis:6379/1
ADMIN_USER=admin
ADMIN_USER_EMAIL=admin@example.org
ADMIN_USER_PASSWORD=change_me
ANTHROPIC_API_KEY=
POSTGRES_DB=django_dev
POSTGRES_USER=django_dev_user
POSTGRES_PASSWORD=django_dev_password
```

**`docker-compose.yml`** -- 5 services:
- `web`: Django dev server (port 8003->8000), mounts code for live reload
- `db`: PostgreSQL 16-alpine with health check
- `redis`: Redis 7-alpine with health check
- `celery-worker`: Celery worker process
- `celery-beat`: Celery beat scheduler

**`Dockerfile`** -- multi-stage build:
1. Stage 1 (Node 20-slim): Install npm deps, run `npm run build:prod`
2. Stage 2 (Python 3.12-slim): Install system deps (libzbar0, libpq5, curl), install Python deps, copy code + built frontend, create non-root user

**`docker-entrypoint.sh`:**
1. Wait for PostgreSQL to be ready
2. Run migrations
3. Load fixture data (grapes)
4. Create superuser if configured
5. Run collectstatic (production only)

### Running

```bash
# Build and start
docker compose build
docker compose up

# Or in background
docker compose up -d

# View logs
docker compose logs -f web

# Stop
docker compose down
```

Access at http://localhost:8003

---

## 24. Docker Production

### Files Needed

**`.env.docker.prod`:**
```bash
DJANGO_DEBUG=False
DJANGO_SETTINGS_MODULE=wine_cellar.conf.docker_prod_settings
SECRET_KEY=generate-a-64-character-random-string-here
DJANGO_ALLOWED_HOSTS=your-server-ip,your-domain.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain.com
SITE_URL=https://your-domain.com
SQL_ENGINE=django.db.backends.postgresql
SQL_DATABASE=wine_cellar_prod
SQL_USER=wine_cellar_user
SQL_PASSWORD=strong-random-password
SQL_HOST=db
SQL_PORT=5432
DATABASE=postgres
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
REDIS_URL=redis://redis:6379/1
ADMIN_USER=admin
ADMIN_USER_EMAIL=your@email.com
ADMIN_USER_PASSWORD=strong-password
ANTHROPIC_API_KEY=sk-ant-api03-your-key
POSTGRES_DB=wine_cellar_prod
POSTGRES_USER=wine_cellar_user
POSTGRES_PASSWORD=strong-random-password
```

**`docker-compose.prod.yml`** differences from dev:
- Uses `gunicorn` instead of Django dev server
- 2 workers, 120s timeout
- `restart: unless-stopped` on all services
- Redis uses AOF persistence
- All services have health checks
- Persistent volumes for postgres, media, static, redis

### Running

```bash
# Build
docker compose -f docker-compose.prod.yml build

# Start
docker compose -f docker-compose.prod.yml up -d

# Check health
docker compose -f docker-compose.prod.yml ps
curl http://localhost:8000/health/

# View logs
docker compose -f docker-compose.prod.yml logs -f web

# Stop
docker compose -f docker-compose.prod.yml down
```

### Generating a Secret Key

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 25. Bare-Metal Production

Running directly on the server without Docker.

### Setup

```bash
# 1. Install system dependencies
sudo apt install python3.11 python3.11-venv nodejs npm \
    postgresql redis-server libzbar0 libpq-dev openssl curl

# 2. Clone and setup
git clone <repo-url>
cd wine-cellar
python3 -m venv venv
source venv/bin/activate
pip install -r requirements/prod.txt
npm install --no-save
npm run build:prod

# 3. Create .env.prod
cp .env.dev-sample .env.prod
# Edit with production values (see Docker Production section for reference)
# Set DJANGO_SETTINGS_MODULE=wine_cellar.conf.prod

# 4. Setup PostgreSQL (if using)
sudo -u postgres createuser wine_cellar_user
sudo -u postgres createdb wine_cellar_prod -O wine_cellar_user
sudo -u postgres psql -c "ALTER USER wine_cellar_user PASSWORD 'your-password';"

# 5. Run migrations
source .env.prod
python manage.py migrate
python manage.py collectstatic --noinput

# 6. Start production server
./run_prod.sh start
```

### Production Server Manager (`run_prod.sh`)

Manages three gunicorn instances:

| Instance | Bind Address | Purpose |
|----------|-------------|---------|
| cloudflared | 127.0.0.1:8000 | Behind Cloudflare tunnel (if you have one) |
| http | 0.0.0.0:80 | Direct LAN access |
| https | 0.0.0.0:443 | HTTPS with self-signed cert |

Commands:
```bash
./run_prod.sh start [instance|all]
./run_prod.sh stop [instance|all]
./run_prod.sh restart [instance|all]
./run_prod.sh status
./run_prod.sh logs [instance|all]
```

You don't need all three. For a simple setup, just use `http`:
```bash
./run_prod.sh start http
```

### Celery in Production (Bare Metal)

Run as systemd services:

```bash
# /etc/systemd/system/celery-worker.service
[Unit]
Description=Celery Worker
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/wine-cellar
ExecStart=/path/to/wine-cellar/venv/bin/celery -A wine_cellar.conf.celery:celery_app worker --loglevel=warning --concurrency=2
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# /etc/systemd/system/celery-beat.service
[Unit]
Description=Celery Beat
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/wine-cellar
ExecStart=/path/to/wine-cellar/venv/bin/celery -A wine_cellar.conf.celery:celery_app beat --loglevel=warning --scheduler django_celery_beat.schedulers:DatabaseScheduler
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable celery-worker celery-beat
sudo systemctl start celery-worker celery-beat
```

---

## 26. HTTPS & SSL Certificates

### Why HTTPS Matters

Mobile browsers require HTTPS to access the camera (for barcode/label scanning). Without HTTPS, the scanner features won't work on phones.

### Self-Signed Certificates (Development/LAN)

The `run_https.sh` script auto-generates self-signed certificates:

```bash
mkdir -p ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout ssl/server.key \
    -out ssl/server.crt \
    -subj "/C=US/ST=State/L=City/O=WineCellar/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:YOUR_LAN_IP"
```

Then run with django-extensions' `runserver_plus`:
```bash
python manage.py runserver_plus 0.0.0.0:8000 \
    --cert-file ssl/server.crt --key-file ssl/server.key
```

Users must accept the browser security warning once.

### Production HTTPS Options

1. **Reverse proxy (nginx/caddy)** -- terminates SSL, forwards to gunicorn on localhost
2. **Self-signed certificates** -- good enough for LAN/meshnet access
3. **Cloudflare tunnel** -- handles SSL automatically (requires Cloudflare account)
4. **Let's Encrypt (certbot)** -- free certificates for public domains

For the simplest setup without any accounts, use self-signed certificates:
```bash
./run_prod.sh start https
```

---

## 27. Backups

### SQLite Backup

```bash
# Hot-copy the database (safe while Django is running)
sqlite3 db.sqlite3 ".backup backup_$(date +%Y%m%d).sqlite3"

# Compress
gzip backup_$(date +%Y%m%d).sqlite3
```

### PostgreSQL Backup

```bash
# Dump
pg_dump -U wine_cellar_user wine_cellar_prod > backup_$(date +%Y%m%d).sql
gzip backup_$(date +%Y%m%d).sql

# Docker
docker compose exec db pg_dump -U wine_cellar_user wine_cellar_prod > backup.sql
```

### Media Files

```bash
tar czf media_backup_$(date +%Y%m%d).tar.gz media/
```

### Automated Backups (Cron)

```bash
# Run daily at 3am
crontab -e
# Add:
0 3 * * * /path/to/wine-cellar/backup.sh >> /var/log/wine_backup.log 2>&1
```

A sample backup script:
```bash
#!/bin/bash
set -e
BACKUP_DIR="/path/to/backups"
DATE=$(date +%Y%m%d_%H%M)
mkdir -p "$BACKUP_DIR"

# Database
sqlite3 /path/to/wine-cellar/db.sqlite3 ".backup $BACKUP_DIR/db_$DATE.sqlite3"
gzip "$BACKUP_DIR/db_$DATE.sqlite3"

# Media
tar czf "$BACKUP_DIR/media_$DATE.tar.gz" -C /path/to/wine-cellar media/

# Prune old backups (keep 30 days)
find "$BACKUP_DIR" -name "*.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

### Cloud Backup (Optional)

The project includes a `backup_to_r2.sh` script for Cloudflare R2, but you can adapt it for any S3-compatible storage, rsync to another machine, or simply keep local backups.

---

## 28. Ongoing Maintenance

### Updating Dependencies

```bash
# Python
pip install --upgrade -r requirements/dev.txt

# Node
npm update
npm run build

# Check for security vulnerabilities
pip audit
npm audit
```

### Adding New Features

1. Create/modify models
2. `python manage.py makemigrations`
3. `python manage.py migrate`
4. Add views and URL patterns
5. Create/update templates
6. If React components needed: add webpack entry point, build
7. Write tests
8. `make lint && make pytest`

### Database Migrations in Production

```bash
# Always back up first
sqlite3 db.sqlite3 ".backup db_pre_migration.sqlite3"

# Then migrate
python manage.py migrate

# If using Docker
docker compose exec web python manage.py migrate
```

### Common Makefile Commands

```bash
make install          # Full install (npm + pip + migrate + build)
make server           # Dev server on port 8003
make watch            # Dev server + frontend rebuild on changes
make pytest           # Run tests (reuses DB for speed)
make pytest-clean     # Reset test DB and run all tests
make lint             # Full lint check
make fixtures         # Load sample data
make coverage         # Generate HTML coverage report
```

---

## 29. Hosting on a Local Machine with Cloudflare Tunnel

This is the recommended approach for exposing a home server to the internet without opening router ports, buying a domain separately, or getting a static IP. Cloudflare Tunnel (cloudflared) creates an outbound-only encrypted connection from your machine to Cloudflare's edge network, which then serves your site to the public internet.

### How It Works

```
[Phone/Browser] --> [Cloudflare Edge] <-- encrypted tunnel <-- [cloudflared on your Pi/server]
                         |                                              |
                    handles HTTPS                              forwards to gunicorn
                    DDoS protection                            on 127.0.0.1:8000
                    caching
```

1. `cloudflared` runs on your local machine and opens a persistent outbound connection to Cloudflare
2. Cloudflare routes incoming requests for your domain through the tunnel to your machine
3. Django/gunicorn listens on `127.0.0.1:8000` (localhost only -- not exposed to the network)
4. Cloudflare handles HTTPS termination, so Django receives plain HTTP
5. No ports need to be opened on your router

### Prerequisites

- A free Cloudflare account (https://dash.cloudflare.com/sign-up)
- A domain name (you can buy one through Cloudflare for ~$10/year, or use one you already own)
- The domain's DNS must be managed by Cloudflare (follow their setup wizard to transfer nameservers)

### Step 1: Install cloudflared

```bash
# Debian/Ubuntu/Raspberry Pi OS
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# Or for x86_64:
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# Verify
cloudflared --version
```

### Step 2: Authenticate with Cloudflare

```bash
cloudflared tunnel login
```

This opens a browser window. Select the domain you want to use. A certificate is saved to `~/.cloudflared/cert.pem`.

### Step 3: Create the Tunnel

```bash
# Create a named tunnel
cloudflared tunnel create wine-cellar

# This outputs a tunnel UUID like: a1b2c3d4-e5f6-7890-abcd-ef1234567890
# A credentials file is saved to ~/.cloudflared/<UUID>.json
```

### Step 4: Configure the Tunnel

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: a1b2c3d4-e5f6-7890-abcd-ef1234567890  # Your tunnel UUID
credentials-file: /home/your-user/.cloudflared/a1b2c3d4-e5f6-7890-abcd-ef1234567890.json

ingress:
  - hostname: wine.yourdomain.com
    service: http://127.0.0.1:8000
  - service: http_status:404  # Catch-all for unmatched requests
```

### Step 5: Create the DNS Record

```bash
cloudflared tunnel route dns wine-cellar wine.yourdomain.com
```

This creates a CNAME record pointing `wine.yourdomain.com` to your tunnel.

### Step 6: Configure Django

In `.env.prod`:

```bash
DJANGO_ALLOWED_HOSTS=wine.yourdomain.com,127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://wine.yourdomain.com
SITE_URL=https://wine.yourdomain.com
DJANGO_SETTINGS_MODULE=wine_cellar.conf.settings
```

Key Django settings that make this work (already in `settings.py`):

```python
# Trust X-Forwarded-Proto from cloudflared
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
```

**Important:** Do NOT use `prod.py` settings when behind cloudflared. The prod settings enable `SECURE_SSL_REDIRECT = True`, which would cause a redirect loop because cloudflared forwards plain HTTP to Django. The base `settings.py` is correct -- it trusts the `X-Forwarded-Proto` header from cloudflared to know the original request was HTTPS.

If you use the docker prod settings (`docker_prod_settings.py`), note that it explicitly sets `SECURE_SSL_REDIRECT = False` for this reason.

### Step 7: Start Everything

```bash
# Start gunicorn (listens on localhost only)
./run_prod.sh start cloudflared

# Start the tunnel
cloudflared tunnel run wine-cellar
```

Your site is now live at `https://wine.yourdomain.com` with full HTTPS, no port forwarding.

### Step 8: Run cloudflared as a System Service

```bash
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

Or create a manual systemd service:

```ini
# /etc/systemd/system/cloudflared.service
[Unit]
Description=Cloudflare Tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=your-user
ExecStart=/usr/bin/cloudflared tunnel --config /home/your-user/.cloudflared/config.yml run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

### How run_prod.sh Handles This

The `run_prod.sh` script has a dedicated `cloudflared` instance that binds gunicorn to `127.0.0.1:8000` (localhost only). This is deliberate -- cloudflared connects to it locally, and there's no reason to expose port 8000 to the network.

```bash
# Start only the cloudflared gunicorn instance
./run_prod.sh start cloudflared

# Check status (also shows if cloudflared tunnel is running)
./run_prod.sh status
```

The status command checks for both the gunicorn process and the cloudflared tunnel process.

### Costs

- Cloudflare account: Free
- Cloudflare Tunnel: Free (included with free plan)
- Domain name: ~$10-15/year (through Cloudflare or any registrar)

### Advantages

- No static IP needed (works behind CGNAT, dynamic IPs)
- No port forwarding on your router
- Free HTTPS with auto-renewing certificates
- DDoS protection included
- Your home IP address is never exposed
- Works from anywhere in the world

### Limitations

- Requires an internet connection (no offline access for remote users)
- Cloudflare's free plan has a 100MB upload limit (fine for wine label photos)
- You depend on Cloudflare's infrastructure

---

## 30. Hosting: LAN-Only Access (No Internet Exposure)

The simplest hosting option. The app is only accessible from devices on your local network (WiFi/Ethernet).

### Setup

```bash
# Start gunicorn on all interfaces, port 80
./run_prod.sh start http
```

Or for HTTPS (needed for camera access on phones):

```bash
# Start gunicorn with self-signed cert on port 443
./run_prod.sh start https
```

### Finding Your Server's IP

```bash
hostname -I | awk '{print $1}'
# Example output: 192.168.1.42
```

### Django Configuration

```bash
# .env.prod
DJANGO_ALLOWED_HOSTS=192.168.1.42,localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://192.168.1.42,https://192.168.1.42
```

### Access

- From any device on the same network: `http://192.168.1.42` (port 80) or `https://192.168.1.42` (port 443)
- First time on HTTPS: accept the self-signed certificate warning in your browser

### Static IP (Recommended)

Configure your router to assign a static IP to your server's MAC address (usually under DHCP reservation in your router settings). This prevents the IP from changing after a reboot.

### mDNS / .local Hostname (Optional)

On Linux with avahi-daemon, your machine is accessible at `hostname.local`:

```bash
sudo apt install avahi-daemon
# Your machine is now reachable at: wine-cellar.local (or whatever your hostname is)
```

Update Django config:
```bash
DJANGO_ALLOWED_HOSTS=wine-cellar.local,192.168.1.42,localhost,127.0.0.1
```

---

## 31. Hosting: VPN/Meshnet Access

Access your home server from anywhere without exposing it to the public internet. This project uses NordVPN's Meshnet feature, but Tailscale and WireGuard work the same way.

### How It Works

A VPN mesh network gives each device a stable IP address on a private overlay network. Your phone and your server join the same mesh, and traffic between them is encrypted end-to-end.

```
[Phone on 4G]                    [Server at home]
  meshnet IP: 100.64.x.x  <-->  meshnet IP: 100.64.y.y
         (encrypted WireGuard tunnel over the internet)
```

### Option A: Tailscale (Simplest)

```bash
# Install on server
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Install on phone/laptop
# Download Tailscale app from App Store / Play Store / tailscale.com
# Sign in with same account
```

Your server gets a stable Tailscale IP (e.g., `100.100.x.x`). Configure Django:

```bash
DJANGO_ALLOWED_HOSTS=100.100.x.x,localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=https://100.100.x.x
```

Start the HTTPS server:
```bash
./run_prod.sh start https
```

The `run_https.sh` and `run_prod.sh` scripts auto-detect meshnet IPs and include them in the self-signed certificate's Subject Alternative Names, so HTTPS will work without certificate errors (after initial trust).

### Option B: NordVPN Meshnet

```bash
# Install NordVPN
sh <(curl -sSf https://downloads.nordcdn.com/apps/linux/install.sh)
nordvpn login
nordvpn meshnet set on

# Get your meshnet IP and hostname
nordvpn meshnet peer list
# Shows: 100.64.x.x and hostname like "my-server.nord"
```

The `run_prod.sh` script auto-detects the NordVPN meshnet interface (`nord-tun`) and includes its IP in generated SSL certificates.

### Option C: WireGuard (Self-Managed)

More setup, but no third-party service dependency:

```bash
sudo apt install wireguard

# Generate keys
wg genkey | tee server_private.key | wg pubkey > server_public.key
```

Create `/etc/wireguard/wg0.conf` on the server, configure peers for each device. This is well-documented elsewhere and beyond the scope of this guide.

### Django Configuration for VPN

```bash
# Include VPN IPs in allowed hosts
DJANGO_ALLOWED_HOSTS=100.64.x.x,my-hostname.nord,192.168.1.42,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://100.64.x.x,https://my-hostname.nord
```

### Combining VPN with Cloudflare Tunnel

You can run both simultaneously. This project's `run_prod.sh` supports this:

```bash
# Start all three gunicorn instances
./run_prod.sh start all

# Or selectively:
./run_prod.sh start cloudflared  # Public internet via Cloudflare
./run_prod.sh start https        # VPN/meshnet via self-signed cert
./run_prod.sh start http         # LAN access
```

Each instance binds to a different address:
- `cloudflared`: 127.0.0.1:8000 (Cloudflare tunnel connects here)
- `http`: 0.0.0.0:80 (LAN access)
- `https`: 0.0.0.0:443 (VPN/meshnet, self-signed cert)

---

## 32. Hosting: Reverse Proxy with Nginx or Caddy

For production deployments, a reverse proxy sits in front of gunicorn. It handles HTTPS termination, static file serving, and connection buffering.

### Option A: Caddy (Simplest, Auto-HTTPS)

Caddy automatically obtains and renews Let's Encrypt certificates if you have a public domain.

```bash
# Install
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

**Caddyfile** (`/etc/caddy/Caddyfile`):

```
wine.yourdomain.com {
    reverse_proxy localhost:8000
}
```

That's it. Caddy handles HTTPS, certificate renewal, HTTP-to-HTTPS redirect, and proxying.

For a self-signed cert (no public domain):
```
{
    auto_https off
}

:443 {
    tls /path/to/ssl/server.crt /path/to/ssl/server.key
    reverse_proxy localhost:8000
}
```

### Option B: Nginx

```bash
sudo apt install nginx
```

**`/etc/nginx/sites-available/wine-cellar`:**

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name wine.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name wine.yourdomain.com;

    # SSL certificates (from Let's Encrypt, self-signed, etc.)
    ssl_certificate /etc/letsencrypt/live/wine.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/wine.yourdomain.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;

    # Max upload size (for wine label photos)
    client_max_body_size 10M;

    # Proxy to gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/wine-cellar /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

For Let's Encrypt certificates:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d wine.yourdomain.com
# Certbot auto-configures nginx and sets up auto-renewal
```

### Note: WhiteNoise vs Nginx for Static Files

This project uses WhiteNoise to serve static files directly from Django/gunicorn. This means you do NOT need to configure nginx to serve `/static/` or `/media/` -- gunicorn handles it. WhiteNoise adds proper cache headers and gzip compression.

If you want nginx to serve static files instead (marginally faster for high traffic):

```nginx
location /static/ {
    alias /path/to/wine-cellar/staticfiles/;
    expires 1y;
    add_header Cache-Control "public, immutable";
}

location /media/ {
    alias /path/to/wine-cellar/media/;
    expires 1d;
}
```

But for a personal app with a handful of users, WhiteNoise is more than sufficient and simpler to maintain.

---

## 33. Hosting: Choosing Your Hardware

This project is designed to run on small, inexpensive hardware.

### Raspberry Pi 4/5 (Recommended for Home Hosting)

| Spec | Minimum | Recommended |
|------|---------|-------------|
| Model | Pi 4 (2GB) | Pi 4/5 (4GB) |
| Storage | 16GB SD card | 32GB+ SD card or USB SSD |
| OS | Raspberry Pi OS Lite (64-bit) | Raspberry Pi OS Lite (64-bit) |

**Why a Pi works well:**
- Low power consumption (~5W idle, ~10W under load)
- Runs 24/7 for pennies/month in electricity
- Silent (no fans on Pi 4)
- Compact -- sits on a shelf or mounts behind your wine rack
- GPIO/camera for hardware integration features

**Performance notes:**
- npm install + webpack build is slow on a Pi (~5-10 minutes). Build on a faster machine and deploy the artifacts, or use Docker with pre-built images.
- SQLite is fine for personal use on a Pi. PostgreSQL adds overhead but handles concurrent access better.
- 2 gunicorn workers is appropriate. Don't go higher on a Pi.

**SD card reliability:**
- SD cards can wear out from frequent writes. Use `log2ram` to reduce SD card writes:
  ```bash
  sudo apt install log2ram
  ```
- Better: boot from a USB SSD (much more reliable and faster)

### Mini PC (Intel NUC, Beelink, etc.)

More powerful than a Pi, still small and quiet:

| Spec | Recommendation |
|------|----------------|
| CPU | Any recent x86_64 |
| RAM | 4GB+ |
| Storage | 128GB+ SSD |
| OS | Ubuntu Server 24.04 LTS or Debian 12 |

Good if you want to run Docker Compose with the full stack (PostgreSQL, Redis, Celery).

### Old Laptop / Desktop

Works fine. Any machine from the last decade with 4GB RAM can run this. Just plug it in, install the OS, and go.

### Cloud VM (If You Don't Want Home Hardware)

Any cloud provider works. Minimum specs:

| Provider | Instance | Cost |
|----------|----------|------|
| Hetzner | CX22 (2 vCPU, 4GB) | ~$4/month |
| DigitalOcean | Basic (1 vCPU, 2GB) | ~$6/month |
| Oracle Cloud | ARM A1 (4 OCPU, 24GB) | Free tier |
| AWS Lightsail | 1 vCPU, 1GB | ~$5/month |

If using a cloud VM, you don't need cloudflared -- just point your domain's DNS at the VM's IP and use Caddy/nginx with Let's Encrypt.

---

## 34. Hosting: Systemd Auto-Start on Boot

Make everything start automatically when the machine powers on.

### Gunicorn Service

```ini
# /etc/systemd/system/wine-cellar.service
[Unit]
Description=Wine Cellar Gunicorn
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/wine-cellar
EnvironmentFile=/path/to/wine-cellar/.env.prod
ExecStart=/path/to/wine-cellar/venv/bin/gunicorn wine_cellar.conf.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers 2 \
    --timeout 120 \
    --worker-class sync
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Celery Worker Service

```ini
# /etc/systemd/system/celery-worker.service
[Unit]
Description=Wine Cellar Celery Worker
After=network-online.target redis.service
Wants=network-online.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/wine-cellar
EnvironmentFile=/path/to/wine-cellar/.env.prod
ExecStart=/path/to/wine-cellar/venv/bin/celery \
    -A wine_cellar.conf.celery:celery_app \
    worker --loglevel=warning --concurrency=2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Celery Beat Service

```ini
# /etc/systemd/system/celery-beat.service
[Unit]
Description=Wine Cellar Celery Beat
After=network-online.target redis.service
Wants=network-online.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/wine-cellar
EnvironmentFile=/path/to/wine-cellar/.env.prod
ExecStart=/path/to/wine-cellar/venv/bin/celery \
    -A wine_cellar.conf.celery:celery_app \
    beat --loglevel=warning \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Cloudflare Tunnel Service

```ini
# /etc/systemd/system/cloudflared.service
[Unit]
Description=Cloudflare Tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=your-user
ExecStart=/usr/bin/cloudflared tunnel --config /home/your-user/.cloudflared/config.yml run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Enable All Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable wine-cellar celery-worker celery-beat cloudflared
sudo systemctl start wine-cellar celery-worker celery-beat cloudflared

# Verify everything is running
sudo systemctl status wine-cellar celery-worker celery-beat cloudflared
```

### Checking Logs

```bash
# Live logs
journalctl -u wine-cellar -f
journalctl -u cloudflared -f

# Last 100 lines
journalctl -u wine-cellar -n 100

# Since last boot
journalctl -u wine-cellar -b
```

---

## 35. Hosting: Firewall Configuration

### Minimum Required Ports

| Port | Protocol | Purpose | Needed When |
|------|----------|---------|-------------|
| 22 | TCP | SSH | Always (for remote management) |
| 80 | TCP | HTTP | LAN access without HTTPS |
| 443 | TCP | HTTPS | LAN/meshnet HTTPS access |
| 8000 | TCP | Gunicorn | Only if no reverse proxy and not using run_prod.sh |
| 8003 | TCP | Dev server | Development only |

**If using cloudflared only:** No inbound ports are required. Cloudflared uses outbound connections only. You can close ports 80 and 443.

### UFW (Ubuntu Firewall)

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH (always)
sudo ufw allow 22/tcp

# If serving directly on LAN
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable
sudo ufw enable
sudo ufw status
```

### For Cloudflare-Tunnel-Only Setup

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH only
sudo ufw enable
```

No other inbound ports needed -- cloudflared handles everything through outbound connections.

---

## 36. Hosting: Monitoring & Health Checks

### Built-In Health Check

The app exposes `GET /health/` which returns HTTP 200. Use this for monitoring.

```bash
# Quick check
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/
# Should return: 200
```

### Simple Cron-Based Monitoring

```bash
# /usr/local/bin/check_wine_cellar.sh
#!/bin/bash
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/ 2>/dev/null)
if [ "$STATUS" != "200" ]; then
    echo "Wine Cellar is DOWN (status: $STATUS)" | mail -s "Wine Cellar Alert" you@email.com
    # Or restart it:
    sudo systemctl restart wine-cellar
fi
```

```bash
chmod +x /usr/local/bin/check_wine_cellar.sh
# Check every 5 minutes
echo "*/5 * * * * /usr/local/bin/check_wine_cellar.sh" | crontab -
```

### Sentry (Error Tracking)

The production requirements include `sentry-sdk`. To enable:

1. Create a free account at https://sentry.io
2. Create a Django project, get the DSN
3. Add to `.env.prod`:
   ```bash
   SENTRY_DSN=https://your-key@o12345.ingest.sentry.io/67890
   ```
4. Initialize in settings (add to `prod.py` or `docker_prod_settings.py`):
   ```python
   import sentry_sdk
   SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
   if SENTRY_DSN:
       sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.1)
   ```

### Docker Health Checks

The Dockerfile includes a built-in health check:
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1
```

Docker Compose prod also has health checks on all services (PostgreSQL, Redis, web).

---

## 37. Putting It All Together: Complete Raspberry Pi Deployment

A step-by-step walkthrough for deploying on a Raspberry Pi with Cloudflare Tunnel for internet access and self-signed HTTPS for local/VPN access.

### 1. Flash the OS

Download Raspberry Pi OS Lite (64-bit) from https://www.raspberrypi.com/software/. Flash to SD card (or USB SSD) using Raspberry Pi Imager. Enable SSH and set your username/password during imaging.

### 2. Initial Setup

```bash
# SSH in
ssh your-user@raspberrypi.local

# Update system
sudo apt update && sudo apt upgrade -y

# Install all dependencies
sudo apt install -y python3 python3-venv python3-pip \
    nodejs npm git sqlite3 libzbar0 openssl curl \
    redis-server

# Optional: reduce SD card wear
sudo apt install -y log2ram
```

### 3. Clone and Build

```bash
cd ~
git clone <your-repo-url> wine-cellar
cd wine-cellar

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements/prod.txt

# Frontend build (slow on Pi -- be patient, ~5-10 minutes)
npm install --no-save
npm run build:prod
```

### 4. Configure the Application

```bash
# Create environment file
cat > .env.prod << 'EOF'
DJANGO_DEBUG=False
SECRET_KEY=GENERATE_THIS_WITH_python3 -c "import secrets; print(secrets.token_urlsafe(48))"
DJANGO_ALLOWED_HOSTS=wine.yourdomain.com,192.168.1.42,100.64.x.x,localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=https://wine.yourdomain.com,https://192.168.1.42,https://100.64.x.x
SITE_URL=https://wine.yourdomain.com
DJANGO_SETTINGS_MODULE=wine_cellar.conf.settings
ADMIN_USER=admin
ADMIN_USER_EMAIL=you@email.com
ADMIN_USER_PASSWORD=your-strong-password
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
EOF

# Edit the file and replace placeholder values
nano .env.prod
```

### 5. Initialize the Database

```bash
source venv/bin/activate
set -a && source .env.prod && set +a

python manage.py migrate
python manage.py loaddata fixtures/grapes.json
python manage.py collectstatic --noinput

# Create admin user
python manage.py shell << 'PYEOF'
import os
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ.get('ADMIN_USER', 'admin')
email = os.environ.get('ADMIN_USER_EMAIL', 'admin@example.org')
password = os.environ.get('ADMIN_USER_PASSWORD', 'change_me')
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print(f'Superuser "{username}" created')
PYEOF
```

### 6. Install and Configure cloudflared

```bash
# Download for ARM64 (Pi 4/5)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb -o /tmp/cloudflared.deb
sudo dpkg -i /tmp/cloudflared.deb

# Authenticate (opens a URL to click in a browser)
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create wine-cellar
# Note the UUID that's output

# Configure tunnel
cat > ~/.cloudflared/config.yml << EOF
tunnel: YOUR-TUNNEL-UUID
credentials-file: /home/your-user/.cloudflared/YOUR-TUNNEL-UUID.json

ingress:
  - hostname: wine.yourdomain.com
    service: http://127.0.0.1:8000
  - service: http_status:404
EOF

# Create DNS record
cloudflared tunnel route dns wine-cellar wine.yourdomain.com
```

### 7. Create Systemd Services

```bash
# Gunicorn
sudo tee /etc/systemd/system/wine-cellar.service << EOF
[Unit]
Description=Wine Cellar
After=network-online.target redis.service
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/wine-cellar
EnvironmentFile=$HOME/wine-cellar/.env.prod
ExecStart=$HOME/wine-cellar/venv/bin/gunicorn wine_cellar.conf.wsgi:application --bind 127.0.0.1:8000 --workers 2 --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Cloudflare Tunnel
sudo tee /etc/systemd/system/cloudflared.service << EOF
[Unit]
Description=Cloudflare Tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
ExecStart=/usr/bin/cloudflared tunnel --config $HOME/.cloudflared/config.yml run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Celery worker (for background tasks)
sudo tee /etc/systemd/system/celery-worker.service << EOF
[Unit]
Description=Wine Cellar Celery Worker
After=network-online.target redis.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/wine-cellar
EnvironmentFile=$HOME/wine-cellar/.env.prod
ExecStart=$HOME/wine-cellar/venv/bin/celery -A wine_cellar.conf.celery:celery_app worker --loglevel=warning --concurrency=2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Celery beat (for scheduled tasks)
sudo tee /etc/systemd/system/celery-beat.service << EOF
[Unit]
Description=Wine Cellar Celery Beat
After=network-online.target redis.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/wine-cellar
EnvironmentFile=$HOME/wine-cellar/.env.prod
ExecStart=$HOME/wine-cellar/venv/bin/celery -A wine_cellar.conf.celery:celery_app beat --loglevel=warning --scheduler django_celery_beat.schedulers:DatabaseScheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### 8. Start Everything

```bash
sudo systemctl daemon-reload
sudo systemctl enable wine-cellar cloudflared celery-worker celery-beat redis
sudo systemctl start wine-cellar cloudflared celery-worker celery-beat

# Verify
sudo systemctl status wine-cellar cloudflared celery-worker celery-beat
curl -s http://localhost:8000/health/  # Should return 200
```

### 9. Set Up Automated Backups

```bash
# Create backup directory
mkdir -p ~/backups

# Create backup script
cat > ~/wine-cellar/backup.sh << 'EOF'
#!/bin/bash
set -e
BACKUP_DIR="$HOME/backups"
DATE=$(date +%Y%m%d_%H%M)
DB_PATH="$HOME/wine-cellar/db.sqlite3"
MEDIA_PATH="$HOME/wine-cellar/media"

mkdir -p "$BACKUP_DIR"

# Database
sqlite3 "$DB_PATH" ".backup $BACKUP_DIR/db_$DATE.sqlite3"
gzip "$BACKUP_DIR/db_$DATE.sqlite3"

# Media
if [ -d "$MEDIA_PATH" ]; then
    tar czf "$BACKUP_DIR/media_$DATE.tar.gz" -C "$HOME/wine-cellar" media/
fi

# Keep last 30 days
find "$BACKUP_DIR" -name "*.gz" -mtime +30 -delete
echo "[$(date)] Backup complete: $DATE"
EOF
chmod +x ~/wine-cellar/backup.sh

# Schedule daily at 3am
(crontab -l 2>/dev/null; echo "0 3 * * * $HOME/wine-cellar/backup.sh >> /var/log/wine_backup.log 2>&1") | crontab -
```

### 10. Configure Firewall

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
# No other ports needed -- cloudflared handles everything
sudo ufw enable
```

### 11. Test It

From your phone or any device:
1. Open `https://wine.yourdomain.com`
2. Log in with admin / your-password
3. Try scanning a barcode (camera should work -- HTTPS is handled by Cloudflare)
4. Add a wine, create a storage location, put bottles in

### What You've Got

- A wine cellar app running on a $50 Raspberry Pi
- Accessible from anywhere via `https://wine.yourdomain.com`
- HTTPS handled automatically by Cloudflare (free)
- No ports open on your router
- Daily automated backups
- Auto-starts on power loss/reboot
- Camera-based barcode/label scanning from your phone
- ~5W power consumption (~$5/year in electricity)

---

## Quick Reference: Minimum Viable Setup

For the absolute fastest path to a running app:

```bash
# Install system deps (Ubuntu/Debian)
sudo apt install python3 python3-venv nodejs npm libzbar0

# Clone and install
git clone <repo-url> && cd wine-cellar
make install

# Create env file
cp .env.dev-sample .env.dev
# Edit ADMIN_USER_PASSWORD in .env.dev

# Load sample data and start
make fixtures
make server
```

Open http://127.0.0.1:8003, log in with admin / your-password.

For Docker:
```bash
docker compose build && docker compose up
```

Open http://localhost:8003, log in with admin / change_me.
