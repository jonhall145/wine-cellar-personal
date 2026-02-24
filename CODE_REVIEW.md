# Code Structure Review

**Date:** 2026-02-24
**Scope:** Full codebase architecture, models, views, tests, and frontend

---

## Executive Summary

The wine-cellar-personal project is a well-organized Django application with a React frontend. The core architecture is sound — clean app separation, good use of Django conventions, and a solid household-based multi-tenancy model. However, there are several areas where targeted improvements would significantly improve maintainability, performance, and safety.

**Top 5 priorities:**
1. Massive code duplication between wine and whisky apps (~80% identical)
2. Bundle sizes are bloated (maps.js is 6.9MB)
3. Missing authorization enforcement on wine/whisky views
4. N+1 query problems in model properties
5. Business logic trapped in fat views instead of service layer

---

## 1. Project Structure

### Strengths
- Clean Django app separation (core, wine, whisky, storage, household, user)
- Good config split (dev/prod/test/docker settings)
- Makefile provides clear developer workflow
- Docker + Raspberry Pi deployment is well thought out
- Pre-commit hooks (husky + lint-staged) enforce quality

### Issues

#### 1.1 Wine/Whisky Duplication (Critical)

The whisky app is a near-complete copy of the wine app. Side-by-side comparison:

| File | Wine | Whisky | Similarity |
|------|------|--------|------------|
| models.py | 789 lines | 991 lines | ~75% identical |
| views.py | 1,950 lines | 1,927 lines | ~80% identical |
| forms.py | 768 lines | 1,010 lines | ~70% identical |
| filters.py | 325 lines | 394 lines | ~65% identical |
| urls.py | 45 paths | 62 paths | ~70% identical |

**Impact:** Every bug fix or feature must be applied twice. The two apps already diverge in subtle ways (inconsistent URL patterns, slightly different field names).

**Recommendation:** Extract shared behavior into abstract base classes or a shared "cellar" app:
- Abstract `BeverageModel` base with wine/whisky-specific subclasses
- Shared `BeverageFormMixin` and `BeverageViewMixin`
- Single set of URL patterns with app-type parameter
- This would eliminate ~2,000 lines of duplicated code

#### 1.2 Storage URLs at Root Level

Storage routes are defined in `wine_cellar/conf/urls.py` rather than having their own `storage/urls.py` included via `include()`. This makes ownership unclear and breaks the Django convention of self-contained apps.

#### 1.3 No Service Layer Convention

Business logic is split between models (properties), views (static methods), and a small `services/` directory. There's no consistent convention for where domain logic lives.

---

## 2. Models

### Strengths
- `UserContentModel` abstract base is a good pattern for multi-tenancy
- Comprehensive unique constraints (23 total)
- Good index coverage on high-traffic queries (28 indexes)
- Proper use of `on_delete` semantics (CASCADE vs SET_NULL chosen thoughtfully)
- Soft delete on `StorageItem` preserves inventory history

### Issues

#### 2.1 N+1 Query Problems in Properties (High)

Multiple Wine model properties trigger individual queries when accessed:

```python
@property
def get_vineyards(self):
    return "\n".join([str(v) for v in self.vineyard.all()])  # query per wine

@property
def get_grapes(self):
    return "\n".join([str(g) for g in self.grapes.all()])  # query per wine
```

Properties `get_vineyards`, `get_grapes`, `get_sources`, `get_attributes`, `get_food_pairings`, `total_stock`, and `get_stock` all trigger queries. In a list view of 50 wines, this could mean 350+ queries.

**Recommendation:** Create a custom manager with `prefetch_related()`:
```python
class WineQuerySet(models.QuerySet):
    def with_related(self):
        return self.select_related('size', 'appellation').prefetch_related(
            'grapes', 'attributes', 'food_pairings', 'vineyard', 'source'
        )
```

#### 2.2 Missing Foreign Key Indexes (High)

Several frequently-queried FKs lack indexes:
- `WineImage.wine` — queried on every detail page
- `DrinkRecord.wine` — queried for consumption history
- `BottleNote.storage_item` — queried on bottle detail
- `WineBarcode.wine` — queried during barcode scans

Django auto-creates indexes on ForeignKey fields, but some older fields or fields with custom configurations may have been missed. Worth verifying with `SHOW INDEX` or Django's `inspectdb`.

#### 2.3 No Custom Managers (Medium)

All models use Django's default manager. Missing opportunities:
- Household-scoped default manager (prevent cross-tenant queries)
- `StorageItem.objects.in_stock()` for the common `deleted=False` filter
- `Wine.objects.with_stock_count()` for annotated queries

#### 2.4 Cascade Deletion Destroys History (Medium)

Deleting a Wine cascades to: DrinkRecord, PriceHistory, DrinkingWindowAlert, ReorderReminder, WineBarcode. This destroys valuable historical data.

**Recommendation:** Consider soft delete on Wine (like StorageItem), or archive patterns for historical records.

#### 2.5 Missing Validators (Low)

- `Wine.price` and `StorageItem.price` allow negative values
- `Wine.vintage` allows future years
- `Wine.abv` has no upper bound validator

#### 2.6 Inconsistent Naming (Low)

- `Wine.vintage` (int) vs `Whisky.vintage_year` (int) — same concept, different names
- `Wine.vineyard` (M2M to producers) — "vineyard" typically means location, not producer

---

## 3. Views

### Strengths
- Good mix of CBVs for CRUD and FBVs for AJAX endpoints
- Rate limiting on create/edit views
- Household app has excellent permission architecture (mixin hierarchy)
- WineDetailView uses proper `select_related` / `prefetch_related`
- API endpoints have proper JSON error handling

### Issues

#### 3.1 Missing Auth Enforcement on Wine/Whisky Views (Critical)

Wine and whisky CBVs do **not** use `LoginRequiredMixin`:

```python
class WineCreateView(FormView):  # No LoginRequiredMixin!
    ...
```

This relies entirely on django-allauth's global configuration. If that configuration changes, views become publicly accessible.

**Recommendation:** Add `LoginRequiredMixin` to every CBV, or create a base `AuthenticatedFormView` that all views inherit from.

#### 3.2 Fat Views with Embedded Business Logic (High)

Several views contain complex business logic that should live in a service layer:

- **`HomePageView.get_context_data()`** — 8 separate database aggregations inline
- **`WineCreateView.process_form_data()`** — 70+ lines creating Wine + barcodes + M2M + storage items
- **`WineCreateView._apply_auto_crop()`** — PIL image processing inline in the view
- **`WineUpdateView.process_form_data()`** — Complex image state management (cleared/unchanged/new)
- **`storage_move_up/storage_move_down`** — Ordering logic that belongs on the Storage model

**Recommendation:** Extract to service classes:
```
services/
  wine_service.py      # create_wine(), update_wine()
  image_service.py     # process_image(), apply_crop()
  stats_service.py     # get_cellar_stats()
```

#### 3.3 Missing Transaction Safety (High)

`WineCreateView.process_form_data()` creates a Wine, then barcodes, then images, then M2M relationships across multiple database calls — without `@transaction.atomic`. If the image save fails, you get a Wine with no images.

`WineUpdateView.process_form_data()` uses `@transaction.atomic` on a static method, which is unusual but functional.

**Recommendation:** Wrap all multi-model operations in `@transaction.atomic`.

#### 3.4 Inconsistent Authorization Patterns (Medium)

| App | Auth Pattern | Household Filtering |
|-----|-------------|-------------------|
| Household | Mixin hierarchy (excellent) | Enforced in mixin dispatch |
| Storage | Manual `get_active_household()` | Per-method, easy to forget |
| Wine | None explicit | Per-method, easy to forget |
| Whisky | None explicit | Per-method, easy to forget |

**Recommendation:** Adopt the household app's mixin pattern across all apps:
```python
class WineCreateView(RequireMemberMixin, FormView):
    ...
```

#### 3.5 Duplicated URL Patterns (Medium)

Wine and whisky have inconsistent URL structures:
- Wine: `stock/add/<int:pk>/` vs Whisky: `whisky/<int:pk>/stock/add/`
- Wine: `bottle/edit/<int:pk>/` vs Whisky: `stock/<int:pk>/edit/`

---

## 4. Tests & Utilities

### Strengths
- Well-structured factory hierarchy with `pytest-factoryboy`
- Smart use of `lazy_attribute` for household propagation
- Environment-based test gating for whisky-specific tests
- Good coverage of household permissions and role hierarchy
- Filter logic is thoroughly tested
- `--reuse-db` for fast iteration

### Issues

#### 4.1 Coverage at 59% (Medium)

The minimum threshold is 59%, which is fairly low. Key gaps:

| Area | Status |
|------|--------|
| Form validation | Limited direct tests |
| Signal handlers | Untested |
| Image processing utils | Untested |
| Management commands | Only `send_drink_reminders` tested |
| Template tags | Partial coverage |
| Error/edge cases in filters | Missing |

**Recommendation:** Target 75% coverage. Prioritize testing:
1. Form validation (especially TomSelect edge cases)
2. Image utility functions (crop, thumbnail, orientation)
3. All management commands
4. Signal-created objects (default storage on household creation)

#### 4.2 No Integration / E2E Tests (Medium)

Tests are primarily unit-level. There are no tests for:
- Full create-wine-with-images flow
- Barcode scan → wine lookup → stock add flow
- Household invite → accept → shared data visibility

Playwright is installed but only used for manual UI checks, not automated test suites.

#### 4.3 Views.py Excluded from Coverage (Low)

```toml
[tool.coverage.run]
omit = ["**/views.py"]
```

Views contain significant business logic (see section 3.2). Excluding them from coverage measurement hides the gap.

---

## 5. Frontend

### Strengths
- TypeScript adoption across most files
- Clean React component structure with hooks
- Good Django-React integration via `data-*` attributes
- CSS custom properties for theming and dark mode
- Mobile-first responsive design
- Proper WASM handling for barcode detection
- Well-configured linting (ESLint + Prettier + Stylelint)

### Issues

#### 5.1 Massive Bundle Sizes (Critical)

| Bundle | Size | Notes |
|--------|------|-------|
| maps.js | 6.82 MB | Leaflet + MapLibre + cluster |
| distillery_map.js | 6.86 MB | Same libs duplicated |
| storage_grid.js | 3.27 MB | React + dnd-kit |
| barcode_scanner.js | 3.22 MB | React + zxing |
| label_scanner.js | 2.93 MB | React + camera |
| base.js | 498 KB | Core bundle |

Maps alone are 13.7MB because Leaflet/MapLibre are duplicated across two bundles.

**Recommendation:** Add `splitChunks` to webpack config:
```javascript
optimization: {
  splitChunks: {
    chunks: 'all',
    cacheGroups: {
      vendor: {
        test: /[\\/]node_modules[\\/]/,
        name: 'vendors',
        chunks: 'all',
      },
      leaflet: {
        test: /[\\/]node_modules[\\/](leaflet|@maplibre)[\\/]/,
        name: 'leaflet-vendor',
        chunks: 'all',
      },
    },
  },
}
```

This should cut map bundle sizes by ~50%.

#### 5.2 TypeScript Safety Gaps (Medium)

- 10 `@ts-ignore` suppressions for Django i18n imports
- Mixed `.jsx` / `.tsx` files in the maps directory
- `any` types used in storage_grid.tsx and vision extraction
- Vision extraction files (`.js`) not typed at all

**Recommendation:**
1. Create `types/django.d.ts` with proper type definitions
2. Convert all `.jsx` to `.tsx`
3. Enable `noImplicitAny: true` in tsconfig

#### 5.3 Missing React Error Boundaries (Medium)

No error boundaries exist. If the barcode scanner, storage grid, or map crashes (e.g., WebGL not supported), the entire page section breaks with no user feedback.

**Recommendation:** Create a generic `ErrorBoundary` component and wrap each mounted React root.

#### 5.4 Small Bundles as Separate Entry Points (Low)

`wine_carousel.js` (4KB) and `storage_view_toggle.js` (7KB) are separate HTTP requests for trivial functionality. These could be merged into `base.js`.

#### 5.5 No Production Source Maps (Low)

`webpack.prod.js` sets `devtool: false`. Production errors will be impossible to debug without source maps.

---

## 6. Architecture Recommendations (Prioritized)

### Tier 1 — High Impact, Moderate Effort

| # | Issue | Effort | Impact |
|---|-------|--------|--------|
| 1 | Add `LoginRequiredMixin` to all wine/whisky CBVs | Small | Security |
| 2 | Add `@transaction.atomic` to multi-model view operations | Small | Data integrity |
| 3 | Add webpack `splitChunks` for vendor deduplication | Small | 50% bundle reduction |
| 4 | Create custom QuerySet with `prefetch_related` for Wine/Whisky | Medium | Eliminate N+1 queries |
| 5 | Adopt household mixin pattern across all apps | Medium | Consistent authorization |

### Tier 2 — High Impact, Higher Effort

| # | Issue | Effort | Impact |
|---|-------|--------|--------|
| 6 | Extract business logic from views to service layer | Large | Maintainability |
| 7 | Extract shared wine/whisky code to abstract base | Large | Eliminate duplication |
| 8 | Increase test coverage to 75%, include views.py | Medium | Reliability |
| 9 | Create TypeScript definitions for Django integration | Small | Type safety |
| 10 | Add React error boundaries | Small | User experience |

### Tier 3 — Lower Priority

| # | Issue | Effort | Impact |
|---|-------|--------|--------|
| 11 | Add missing model validators (price, vintage) | Small | Data quality |
| 12 | Standardize URL patterns across wine/whisky | Medium | Developer experience |
| 13 | Convert .jsx to .tsx in maps components | Small | Type safety |
| 14 | Soft delete on Wine model (preserve history) | Medium | Data preservation |
| 15 | Add integration/E2E tests with Playwright | Large | Confidence |
| 16 | Merge small JS bundles into base.js | Small | Fewer HTTP requests |
| 17 | Add webpack-bundle-analyzer | Small | Visibility |
| 18 | Move storage URLs to proper app include | Small | Convention |

---

## 7. What's Working Well

Worth noting the things this codebase does right:

- **Household multi-tenancy** is well-designed with proper role hierarchy
- **Mobile-first CSS** with dark mode support
- **Vision extraction** (AI label reading) is a sophisticated feature, well-isolated in services
- **Storage grid** with drag-and-drop is polished
- **Pre-commit quality gates** prevent common issues
- **Docker deployment** with Raspberry Pi support
- **Factory-based tests** are clean and maintainable
- **Rate limiting** on mutation endpoints
- **Soft delete** on storage items preserves inventory history
- **Caching** on filter choices prevents repeated DB hits
