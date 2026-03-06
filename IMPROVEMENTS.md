# Wine Cellar Improvement Plan

This document outlines recommended improvements for the Wine Cellar project, organized by priority.

## Current State Summary

| Aspect | Status | Notes |
|--------|--------|-------|
| Architecture | Excellent | Well-organized Django apps |
| Code Quality | Good | Some large files need splitting |
| Security | Fair | User isolation good, missing headers |
| Testing | Good | Missing E2E tests |
| Performance | Fair | No caching, potential N+1 queries |

---

## Priority 1: Security Hardening

### 1.1 Add Security Headers Middleware

**Problem:** No CSP, X-Frame-Options, or other security headers configured.

**Solution:** Add to `settings.py`:

```python
# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# For production only
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

**Files:** `wine_cellar/conf/settings.py`, `wine_cellar/conf/prod.py`

### 1.2 Implement Rate Limiting

**Problem:** Vision extraction and barcode endpoints have no rate limits, vulnerable to abuse.

**Solution:** Add `django-ratelimit` to key endpoints:

```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key='user', rate='10/m', method='POST')
def extract_wine_from_vision(request):
    ...
```

**Files:** `wine_cellar/apps/wine/views.py`

### 1.3 Fix Wildcard Imports

**Problem:** `from .settings import *` makes it unclear which settings are overridden.

**Solution:** Use explicit imports or a settings class pattern.

**Files:** `wine_cellar/conf/prod.py`, `wine_cellar/conf/dev.py`

---

## Priority 2: Performance Optimization

### 2.1 Fix N+1 Queries

**Problem:** Homepage and wine list views have potential N+1 query issues.

**Locations:**
- `wine_cellar/apps/wine/views.py:HomePageView` - Multiple aggregations
- `Wine.image_thumbnails` property - Iterates without prefetch

**Solution:**

```python
# In WineListView
def get_queryset(self):
    return (
        Wine.objects.filter(user=self.request.user, deleted=False)
        .select_related("user")
        .prefetch_related("grapes", "attributes", "food_pairings", "images")
        .order_by("-created")
    )
```

### 2.2 Add Caching Layer

**Problem:** No caching configured, repeated queries for same data.

**Solution:** Configure Redis cache in `settings.py`:

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/1"),
    }
}
```

Cache expensive operations:
- Homepage statistics
- User wine counts
- Storage availability

### 2.3 Add Database Indexes

**Problem:** Missing indexes on frequently sorted fields.

**Solution:** Add to Wine model:

```python
class Meta:
    indexes = [
        models.Index(fields=["-created"]),
        models.Index(fields=["drink_by"]),
        models.Index(fields=["user", "deleted"]),
    ]
```

---

## Priority 3: Code Quality

### 3.1 Split Large Views File

**Problem:** `wine_cellar/apps/wine/views.py` is 1,292 lines.

**Solution:** Split into modules:

```
wine_cellar/apps/wine/views/
    __init__.py          # Re-exports for backwards compatibility
    wine_views.py        # Wine CRUD views
    ajax_views.py        # Barcode, vision extraction
    home_views.py        # Homepage
    tasting_views.py     # Tasting notes
```

### 3.2 Extract Service Layer

**Problem:** Business logic scattered in views.

**Solution:** Create service modules:

```
wine_cellar/apps/wine/services/
    barcode_service.py   # Already exists as BarcodeScanner
    vision_service.py    # Already exists as WineVisionExtractor
    wine_service.py      # Wine creation, deletion logic
    reminder_service.py  # Drink reminder logic
```

### 3.3 Add Type Hints

**Problem:** Limited type hints reduce IDE support and catch fewer bugs.

**Solution:** Add type hints to key modules:

```python
def get_queryset(self) -> QuerySet[Wine]:
    ...

def process_form_data(self, user: User, data: dict[str, Any]) -> Wine:
    ...
```

---

## Priority 4: Testing Improvements

### 4.1 Add E2E Tests

**Problem:** No browser-based tests for critical user flows.

**Solution:** Add Playwright tests:

```
tests/e2e/
    test_wine_creation.py    # Full wine add flow
    test_barcode_scan.py     # Barcode scanning
    test_authentication.py   # Login/logout/register
```

### 4.2 Set Coverage Threshold

**Problem:** No minimum coverage enforced.

**Solution:** Add to `pyproject.toml`:

```toml
[tool.coverage.report]
fail_under = 80
show_missing = true
```

### 4.3 Add Integration Tests

**Problem:** Missing tests for email, image processing, external APIs.

**Files to create:**
- `tests/test_emails.py`
- `tests/test_image_processing.py`
- `tests/test_vision_extraction.py`

---

## Priority 5: Logging & Monitoring

### 5.1 Configure Structured Logging

**Problem:** No logging configuration.

**Solution:** Add to `settings.py`:

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "wine_cellar": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
```

### 5.2 Add Audit Logging

**Problem:** No audit trail for data modifications.

**Solution:** Log critical operations:

```python
import logging

logger = logging.getLogger("wine_cellar.audit")

def form_valid(self, form):
    wine = self.process_form_data(...)
    logger.info(
        "Wine created",
        extra={"user_id": self.request.user.id, "wine_id": wine.id}
    )
```

### 5.3 Integrate Error Tracking

**Problem:** No production error visibility.

**Solution:** Add Sentry integration:

```python
import sentry_sdk

sentry_sdk.init(
    dsn=env("SENTRY_DSN"),
    traces_sample_rate=0.1,
)
```

---

## Priority 6: Documentation

### 6.1 API Documentation

**Problem:** AJAX endpoints not documented.

**Solution:** Create `docs/api.md`:

```markdown
## Endpoints

### POST /wine/barcode/scan/
Scan barcode and lookup wine information.

**Request:**
- `image`: Base64 encoded image

**Response:**
- `barcode`: Detected barcode string
- `wine_data`: Wine information if found
```

### 6.2 Environment Variables Documentation

**Problem:** Required env vars scattered across files.

**Solution:** Create `docs/environment.md` listing all variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| SECRET_KEY | Yes | - | Django secret key |
| DATABASE_URL | No | SQLite | Database connection |
| ANTHROPIC_API_KEY | No | - | For vision extraction |

### 6.3 Add CONTRIBUTING.md

**Solution:** Standard contributing guidelines with:
- Development setup
- Code style (Black, isort, flake8)
- Testing requirements
- PR process

---

## Priority 7: Feature Enhancements

### 7.1 Data Export

**Problem:** No way to export wine collection.

**Solution:** Add export views:

```python
class WineExportView(LoginRequiredMixin, View):
    def get(self, request, format):
        wines = Wine.objects.filter(user=request.user, deleted=False)
        if format == "csv":
            return self.export_csv(wines)
        elif format == "json":
            return self.export_json(wines)
```

### 7.2 Customizable Drink Reminders

**Problem:** Fixed 14-day advance warning only.

**Solution:** Add to UserSettings:

```python
reminder_days_before = models.PositiveIntegerField(default=14)
reminder_enabled = models.BooleanField(default=True)
```

### 7.3 Bulk Operations

**Problem:** Can only edit wines one at a time.

**Solution:** Add bulk actions to wine list:
- Bulk delete
- Bulk move to storage
- Bulk update drink_by date

### 7.4 Statistics Dashboard

**Problem:** Limited analytics.

**Solution:** Add stats page with:
- Wine by type chart
- Wine by country map
- Purchase trends over time
- Value by storage location

---

## User-Reported Issues (Bugs & UX)

Issues collected from user testing sessions:

| Issue | Status | Notes |
|-------|--------|-------|
| Currency displays as "X£" instead of "£X" | Fixed | Commit 06edecd |
| Storage dropdowns don't respect reordered storage lists | Open | |
| Country rarely autofills correctly (TomSelect issue?) | Open | |
| Clear and filter buttons misaligned in wine filter page | Fixed | Commit 649b824 |
| Maps should show wines in region, not just country | Open | Would require region data |
| Star rating in wine add is free text, should be dropdown | Fixed | Now uses TypedChoiceField with star choices |
| Option to display more wines per page | Fixed | Added pagination options |
| Wines with no data should sort to end of date queries | Open | |
| "More" button on left does nothing | Open | Investigate |
| Map: outline/choropleth format | Fixed | Commit 7d16310 |

---

## Implementation Timeline

| Phase | Items | Effort |
|-------|-------|--------|
| Phase 1 | Security (1.1-1.3) | Small |
| Phase 2 | Performance (2.1-2.3) | Medium |
| Phase 3 | Code Quality (3.1-3.3) | Medium |
| Phase 4 | Testing (4.1-4.3) | Medium |
| Phase 5 | Logging (5.1-5.3) | Small |
| Phase 6 | Documentation (6.1-6.3) | Small |
| Phase 7 | Features (7.1-7.4) | Large |

---

## Quick Wins (Can Do Today)

1. Add security headers to settings.py
2. Set coverage threshold in pyproject.toml
3. Create docs/environment.md
4. Add `prefetch_related` to wine list queryset
5. Create CONTRIBUTING.md from template

---

## Dependencies to Add

```txt
# requirements/base.txt
django-ratelimit>=4.1.0    # Rate limiting
python-json-logger>=2.0.0  # Structured logging
sentry-sdk>=1.40.0         # Error tracking (optional)
```

---

## Progress Log

_Last updated: 2026-03-06_

### Overall Status

| Priority | Items | Status |
|----------|-------|--------|
| 1 (Security) | 3/3 | **Complete** |
| 2 (Performance) | 3/3 | **Complete** |
| 3 (Code Quality) | 3/3 | **Complete** |
| 4 (Testing) | 2/3 | **Mostly complete** — missing `test_emails.py`, coverage threshold at 59% (target 80%) |
| 5 (Logging) | 3/3 | **Complete** |
| 6 (Documentation) | 3/3 | **Complete** |
| 7 (Features) | 3/4 | **Mostly complete** — stats dashboard is partial (homepage stats only, no dedicated page) |

### Priority 1: Security — Done

- [x] 1.1 Security headers added to `settings.py` (lines 255-271) and `prod.py` (lines 63-68)
- [x] 1.2 Rate limiting via `django-ratelimit==4.1.0` on scan/vision/wine endpoints
- [x] 1.3 Wildcard imports replaced with explicit imports in `prod.py` and `docker_settings.py`

### Priority 2: Performance — Done

- [x] 2.1 N+1 queries fixed — `Wine.with_related()` queryset method, `select_related`/`prefetch_related` in views
- [x] 2.2 Caching — LocMemCache (dev), Redis (docker/prod) with 1hr timeout
- [x] 2.3 Database indexes — comprehensive indexes on Wine, Appellation, WineBarcode, DrinkRecord, etc.

### Priority 3: Code Quality — Done

- [x] 3.1 Views split into `wine_cellar/apps/wine/views/` with 12 modules (ajax, bulk, cellar, drink, health, home, map, reminders, scan, wine_crud, wishlist)
- [x] 3.2 Service layer at `wine_cellar/apps/wine/services/` (barcode_service.py, vision_extraction.py)
- [x] 3.3 Type hints added to key services and utilities (partial but sufficient)

### Priority 4: Testing — Mostly Done

- [x] 4.1 E2E tests in `tests/e2e/` (test_auth.py, test_wine_crud.py, test_wine_list.py)
- [x] 4.2 Coverage threshold set in pyproject.toml (`fail_under = 59` — below 80% target)
- [ ] 4.3 Integration tests — `test_image_processing.py` and `test_vision_extraction.py` exist, but `test_emails.py` still missing

### Priority 5: Logging — Done

- [x] 5.1 Structured logging configured in settings.py (lines 276-336), JSON formatter in docker prod
- [x] 5.2 Audit logging via `wine_cellar.audit` logger in views
- [x] 5.3 Sentry integration via `sentry-sdk==2.48.0` in prod requirements, conditional on `SENTRY_DSN`

### Priority 6: Documentation — Done

- [x] 6.1 API docs at `docs/api.md`
- [x] 6.2 Environment docs at `docs/environment.md`
- [x] 6.3 `CONTRIBUTING.md` created

### Priority 7: Features — Mostly Done

- [x] 7.1 Data export — CSV and JSON export in `wine_cellar/apps/wine/export.py` and `views/ajax.py`
- [x] 7.2 Drink reminders — `reminder_enabled` and `reminder_years_before` fields on UserSettings (note: uses years not days)
- [x] 7.3 Bulk operations — `bulk_action_view()` in `views/bulk.py`
- [ ] 7.4 Statistics dashboard — homepage stats with caching exist, but no dedicated stats page with charts/maps/trends

### Dependency Bumps (2026-03-06)

- [x] Django 6.0.2 → 6.0.3 (fixes CVE: uncontrolled resource consumption, race condition)
- [x] django-allauth 65.13.1 → 65.14.1 (fixes open redirect vulnerability)
- [x] immutable 5.1.4 → 5.1.5 (JS dev dependency)
- [x] serialize-javascript overridden to 7.0.3 (RCE fix, PR #81)

---

## Notes

- All changes should maintain backwards compatibility
- Run full test suite after each phase
- Deploy security changes first before any features
- Consider feature flags for larger changes
- [Implemented 2026-01-20] Robust barcode scanning (whitespace/leading zero handling) added to `BarcodeScanner`.
