# Performance Fixes for Wine Cellar

This document outlines performance issues diagnosed on 2026-01-13 and their recommended fixes.

---

## Implemented Fixes (Quick Wins)

The following changes have been made to improve performance:

### 1. DEBUG Mode Default Changed
**File:** `wine_cellar/conf/settings.py:34`

Changed default from `True` to `False`:
```python
DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"
```
- Production deployments now default to DEBUG=False (safer, faster)
- Development still works via `.env.dev` which sets `DJANGO_DEBUG=True`

### 2. GZip Compression Enabled
**File:** `wine_cellar/conf/settings.py:72`

Added GZip middleware at the top of the middleware stack:
```python
MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",  # Compress responses
    ...
]
```
- Compresses HTML responses automatically
- Reduces bandwidth for all dynamic pages

### 3. WhiteNoise Static File Compression
**File:** `wine_cellar/conf/settings.py:185-192`

Configured WhiteNoise to compress and cache static files:
```python
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```
- Auto-generates `.gz` and `.br` compressed versions of static files
- Serves compressed files with cache headers
- Run `python manage.py collectstatic` to generate compressed files

### 4. Development Script Updated
**File:** `run_local.sh:33-34`

Explicitly sets DEBUG=True for development:
```bash
export DJANGO_DEBUG=True
```

### 5. Lazy Loading Already Implemented
Heavy JS bundles are already loaded only on pages that need them via `{% block extra_js %}`:
- `maps.js` (2.8MB) - only on `/wine/map/`
- `barcode_scanner.js` (1.3MB) - only on `/scan/`
- `label_scanner.js` (1.2MB) - only on `/label-scan/`
- `storage_grid.js` (1.2MB) - only on storage detail pages

### To Apply Changes

```bash
# Rebuild frontend for production (minified)
npm run build:prod

# Collect static files with compression
python manage.py collectstatic --noinput

# Restart server
# (for systemd): sudo systemctl restart wine-cellar
# (for dev): ./run_local.sh
```

### Expected Improvements

| Change | Impact |
|--------|--------|
| DEBUG=False | ~10-20% faster responses (no query logging) |
| GZip middleware | ~60-70% smaller HTML responses |
| WhiteNoise compression | ~60-70% smaller static files |
| Production webpack build | ~60-70% smaller JS bundles |

---

## Implemented Fixes (Medium-Term - Database Optimization)

The following N+1 query issues and inefficient database access patterns have been fixed:

### 1. Wine.total_stock N+1 Query Fixed
**Files:** `wine_cellar/apps/wine/views.py`, `wine_cellar/apps/wine/templates/wine_card.html`, `wine_cellar/apps/wine/templates/wine_detail.html`

**Problem:** The `total_stock` property executed a separate database query for each wine in list views.

**Solution:** Added `stock_count` annotation to querysets:

```python
# In WineListView and WineDetailView
qs = qs.annotate(
    stock_count=Count(
        "storageitem",
        filter=Q(storageitem__deleted=False)
    )
)
```

Templates now use `{% firstof wine.stock_count wine.total_stock %}` for backwards compatibility.

**Impact:** Reduces queries from N+1 to 1 on wine list pages (e.g., 100 wines = 100 queries down to 1).

### 2. HomePageView Query Consolidation
**File:** `wine_cellar/apps/wine/views.py:34-80`

**Problem:** 10+ separate database queries to calculate dashboard statistics.

**Solution:** Consolidated Wine statistics into a single aggregate query:

```python
wine_stats = Wine.objects.filter(user=user).aggregate(
    total_wines=Count("id"),
    wines_in_stock=Count("id", filter=Q(storageitem__deleted=False), distinct=True),
    countries=Count("country", distinct=True),
    oldest_vintage=Min("vintage", filter=Q(vintage__isnull=False)),
    youngest_vintage=Max("vintage", filter=Q(vintage__isnull=False)),
    overdue_count=Count("id", filter=Q(...), distinct=True),
    upcoming_count=Count("id", filter=Q(...), distinct=True),
)
```

Also consolidated DrinkRecord queries:

```python
drink_stats = DrinkRecord.objects.filter(user=user).aggregate(
    total_consumed=Count("id"),
    avg_rating=Avg("rating", filter=Q(rating__isnull=False))
)
```

**Impact:** Reduces homepage queries from 10+ to 4 (one for wines, one for drinks, one for storage, one for reminders).

### 3. ReorderRemindersView N+1 Query Fixed
**File:** `wine_cellar/apps/wine/views.py:1032-1052`

**Problem:** Called `reminder.wine.total_stock` in a loop, causing N queries.

**Solution:** Added annotation to the reminders queryset:

```python
reminders = ReorderReminder.objects.filter(
    user=user, is_active=True
).select_related("wine").annotate(
    current_stock=Count(
        "wine__storageitem",
        filter=Q(wine__storageitem__deleted=False)
    )
)
```

**Impact:** Reduces queries from N+1 to 1 for reminders page.

### 4. CellarValueView Double Iteration Fixed
**File:** `wine_cellar/apps/wine/views.py:847-866`

**Problem:** Iterated over `storage_items` twice (once for country stats, once for type stats).

**Solution:** Combined into single iteration:

```python
for item in storage_items.select_related("wine"):
    country = item.wine.country_name if item.wine.country else "Unknown"
    wine_type = item.wine.get_type if item.wine.wine_type else "Unknown"

    # Calculate both country and type stats in same loop
    # ...
```

**Impact:** Reduces database access by 50% on cellar value page.

### Summary of Database Optimizations

| View | Before | After | Improvement |
|------|--------|-------|-------------|
| WineListView (10 wines) | 11 queries | 1 query | ~91% reduction |
| HomePageView | 10+ queries | 4 queries | ~60% reduction |
| ReorderRemindersView (5 reminders) | 6 queries | 1 query | ~83% reduction |
| CellarValueView | 2 iterations | 1 iteration | 50% faster |

---

## Remaining Recommendations

### Infrastructure

If experiencing slow response times under load:

1. **Increase VM RAM to 2GB minimum** (recommended 4GB)
2. **Tune swap behavior** (temporary mitigation):
   ```bash
   sudo sysctl vm.swappiness=10
   echo "vm.swappiness=10" | sudo tee -a /etc/sysctl.conf
   ```

### Database

Consider PostgreSQL for production deployments:
- Better concurrent access
- More advanced query optimization
- Full-text search capabilities

### Monitoring

Monitor performance with:

```bash
# Check response times
for url in "/" "/wine/" "/storage/"; do
  echo "Testing $url:"
  curl -s -w "  time: %{time_total}s\n" -o /dev/null "http://localhost:8000$url"
done

# Check memory usage
free -h
```

---

## References

- [Django Database Optimization](https://docs.djangoproject.com/en/5.0/topics/db/optimization/)
- [Webpack Code Splitting](https://webpack.js.org/guides/code-splitting/)
- [Django select_related and prefetch_related](https://docs.djangoproject.com/en/5.0/ref/models/querysets/#select-related)

---

*Last updated: 2026-01-14*
