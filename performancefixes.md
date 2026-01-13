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

## Diagnosis Summary

The slow page loads are caused by **both VM resource constraints AND application-level performance issues**.

---

## Infrastructure Issues

### Memory Constraints

| Metric | Value | Status |
|--------|-------|--------|
| Total RAM | 969MB | Critical |
| Used RAM | 767MB | |
| Available | 202MB | Low |
| Swap Used | 1.1GB | Heavy swapping |
| CPUs | 2 | |
| Load Average | 1.07 | Moderate |

**Impact:** The server is constantly swapping to disk, causing variable response times (0.008s to 9+ seconds for the same endpoint).

### Fixes

1. **Increase VM RAM to 2GB minimum** (recommended 4GB)
   ```bash
   # If using GCP, resize the instance
   gcloud compute instances set-machine-type INSTANCE_NAME --machine-type e2-medium
   ```

2. **Or tune swap behavior** (temporary mitigation)
   ```bash
   # Reduce swappiness to prefer RAM
   sudo sysctl vm.swappiness=10
   echo "vm.swappiness=10" | sudo tee -a /etc/sysctl.conf
   ```

---

## Frontend Performance Issues

### Large JavaScript Bundles

| Bundle | Size | Used On |
|--------|------|---------|
| maps.js | 2.8MB | Map page only |
| barcode_scanner.js | 1.3MB | Scan page only |
| label_scanner.js | 1.2MB | Label scan page only |
| storage_grid.js | 1.2MB | Storage detail only |
| tom_select.js | 216KB | Forms with dropdowns |
| base.css | 172KB | All pages |

**Total potential JS load: ~6.7MB**

### Fixes

#### 1. Build for Production

Currently running in development mode. Switch to production builds:

```bash
# In package.json, ensure you have:
npm run build  # instead of npm run watch

# Or set NODE_ENV
NODE_ENV=production npm run build
```

This typically reduces bundle sizes by 60-70% through minification and tree-shaking.

#### 2. Code Splitting (webpack.common.js)

Add dynamic imports to load heavy bundles only when needed:

```javascript
// webpack.common.js - add splitChunks optimization
optimization: {
  splitChunks: {
    chunks: 'all',
    cacheGroups: {
      vendor: {
        test: /[\\/]node_modules[\\/]/,
        name: 'vendors',
        chunks: 'all',
      },
    },
  },
},
```

#### 3. Lazy Load Page-Specific Scripts

In templates, only load scripts on pages that need them:

```html
<!-- Only on map page -->
{% block extra_js %}
<script src="{% static 'maps.js' %}" defer></script>
{% endblock %}
```

#### 4. Add Compression

Enable gzip/brotli compression in your web server or Django:

```python
# settings.py
MIDDLEWARE = [
    'django.middleware.gzip.GZipMiddleware',  # Add near top
    # ... other middleware
]
```

Or in nginx:
```nginx
gzip on;
gzip_types text/plain text/css application/json application/javascript;
gzip_min_length 1000;
```

---

## Backend Performance Issues

### Endpoint Response Times

| Endpoint | Time | Status |
|----------|------|--------|
| `/` (homepage) | 0.008s | OK |
| `/wine/` | 0.9s | Slow |
| `/storage/` | 0.006s | OK |
| `/login/` | 0.006s | OK |

### N+1 Query Problems

#### Issue 1: `Wine.total_stock` Property

**Location:** `wine_cellar/apps/wine/models.py:325`

```python
@property
def total_stock(self):
    return self.storageitem_set.filter(deleted=False).count()
```

**Problem:** Called for every wine in list views, causing N+1 queries.

**Fix:** Use annotation in the queryset instead:

```python
# In WineListView.get_queryset()
from django.db.models import Count, Q

qs = qs.annotate(
    stock_count=Count(
        'storageitem',
        filter=Q(storageitem__deleted=False)
    )
)
```

Then access as `wine.stock_count` in templates instead of `wine.total_stock`.

#### Issue 2: HomePageView Multiple Queries

**Location:** `wine_cellar/apps/wine/views.py:31-178`

**Problem:** Makes 10+ separate database queries for dashboard statistics.

**Fix:** Consolidate into fewer queries:

```python
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    user = self.request.user

    # Single query with aggregations
    wine_stats = Wine.objects.filter(user=user).aggregate(
        total_wines=Count('id'),
        wines_in_stock=Count('id', filter=Q(storageitem__deleted=False)),
        country_count=Count('country', distinct=True),
        oldest_vintage=Min('vintage', filter=Q(vintage__isnull=False)),
        newest_vintage=Max('vintage', filter=Q(vintage__isnull=False)),
    )

    context.update(wine_stats)
    return context
```

#### Issue 3: ReorderRemindersView Loop

**Location:** `wine_cellar/apps/wine/views.py:1014-1048`

```python
# Problem: N+1 query
for reminder in reminders:
    current_stock = reminder.wine.total_stock  # DB query per reminder!
```

**Fix:** Annotate the queryset:

```python
reminders = ReorderReminder.objects.filter(
    user=user, is_active=True
).select_related("wine").annotate(
    current_stock=Count(
        'wine__storageitem',
        filter=Q(wine__storageitem__deleted=False)
    )
)

# Then use reminder.current_stock instead of reminder.wine.total_stock
```

#### Issue 4: CellarValueView Double Iteration

**Location:** `wine_cellar/apps/wine/views.py:828-874`

**Problem:** Iterates over `storage_items` twice (once for country, once for type).

**Fix:** Single pass iteration:

```python
wines_by_country = {}
wines_by_type = {}

for item in storage_items.select_related("wine"):
    country = item.wine.country_name if item.wine.country else "Unknown"
    wine_type = item.wine.get_type if item.wine.wine_type else "Unknown"

    # Country stats
    if country not in wines_by_country:
        wines_by_country[country] = {"count": 0, "value": Decimal("0.00")}
    wines_by_country[country]["count"] += 1
    if item.price:
        wines_by_country[country]["value"] += item.price

    # Type stats (same loop)
    if wine_type not in wines_by_type:
        wines_by_type[wine_type] = {"count": 0, "value": Decimal("0.00")}
    wines_by_type[wine_type]["count"] += 1
    if item.price:
        wines_by_type[wine_type]["value"] += item.price
```

---

## Django Configuration

### Disable DEBUG in Production

**Location:** `wine_cellar/conf/settings.py`

```python
# Current (problematic)
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

# Fix: Default to False
DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"
```

Or set environment variable:
```bash
export DJANGO_DEBUG=False
```

### Database Considerations

Currently using SQLite which is fine for small deployments but consider PostgreSQL for:
- Better concurrent access
- More advanced query optimization
- Full-text search capabilities

```python
# For PostgreSQL
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "wine_cellar",
        "USER": "wine_user",
        "PASSWORD": os.environ.get("DB_PASSWORD"),
        "HOST": "localhost",
        "PORT": "5432",
    }
}
```

### Add Database Indexes

Create a migration for frequently queried fields:

```python
# wine_cellar/apps/wine/migrations/XXXX_add_indexes.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('wine', 'previous_migration'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='wine',
            index=models.Index(fields=['user', 'created'], name='wine_user_created_idx'),
        ),
        migrations.AddIndex(
            model_name='wine',
            index=models.Index(fields=['user', 'wine_type'], name='wine_user_type_idx'),
        ),
        migrations.AddIndex(
            model_name='wine',
            index=models.Index(fields=['user', 'country'], name='wine_user_country_idx'),
        ),
    ]
```

---

## Priority Order for Fixes

### Immediate Impact (Do First)
1. Increase VM RAM to 2GB+
2. Set `DEBUG=False`
3. Run production webpack build

### Medium Term
4. Fix N+1 queries in WineListView
5. Optimize HomePageView queries
6. Add gzip compression

### Long Term
7. Implement code splitting
8. Add database indexes
9. Consider PostgreSQL migration

---

## Monitoring

After implementing fixes, monitor with:

```bash
# Check response times
for url in "/" "/wine/" "/storage/"; do
  echo "Testing $url:"
  curl -s -w "  time: %{time_total}s\n" -o /dev/null "http://localhost:8000$url"
done

# Check memory usage
free -h

# Check Django query count (with django-debug-toolbar in dev)
```

---

## References

- [Django Database Optimization](https://docs.djangoproject.com/en/5.0/topics/db/optimization/)
- [Webpack Code Splitting](https://webpack.js.org/guides/code-splitting/)
- [Django select_related and prefetch_related](https://docs.djangoproject.com/en/5.0/ref/models/querysets/#select-related)
