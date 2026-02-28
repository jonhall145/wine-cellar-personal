# Code Structure Review

**Date:** 2026-02-24
**Updated:** 2026-02-26
**Scope:** Full codebase architecture, models, views, tests, and frontend

---

## Progress Tracker

| # | Issue | Status | Notes |
|---|-------|--------|-------|
| 1 | Auth enforcement on wine/whisky views | ✅ Resolved | `LoginRequiredMiddleware` enforces globally (v0.0.2) |
| 2 | `@transaction.atomic` on multi-model operations | ✅ Done | Both `WineCreateView` and `WineUpdateView` now use `@transaction.atomic` |
| 3 | Webpack `splitChunks` for vendor dedup | ✅ Done | PR #58 — `react-vendors` and `leaflet-vendors` chunks in `webpack.common.js` |
| 4 | Custom QuerySets with `prefetch_related` | ✅ Done | `WineQuerySet`, `WhiskyQuerySet`, `StorageItemQuerySet`, `WhiskyStorageItemQuerySet` with `HouseholdQuerySet` base |
| 5 | Adopt household mixin pattern across all apps | ✅ Done | `RequireHouseholdMixin` / `RequireMemberMixin` on all wine/whisky CBVs |
| 6 | Extract service layer from views | ❌ Open | Business logic still in views; only `WineVisionExtractor` is service-extracted |
| 7 | Extract shared wine/whisky abstract base | 🔄 Phase 5 | Phase 1: foundation (mixins, JS merge, storage URLs). Phase 2: 13 base views + 2 AJAX helpers to core. Phase 3: shared filters, forms, Create/Update views to core (~620 lines saved). Phase 4: extract_vision_ajax, LabelScanView, HomePageView, MergeConfirmView, filter factory to core (~450 lines saved). Phase 5: templates |
| 8 | Increase test coverage to 75% | ❌ Open | Still at 59% threshold; `views.py` still excluded from coverage |
| 9 | TypeScript definitions for Django | ✅ Done | `types/django.d.ts` with proper `declare module` |
| 10 | React error boundaries | ✅ Done | `ErrorBoundary` component wrapping all 5 React mount points |
| 11 | Missing model validators (price, ABV) | ✅ Done | `MinValueValidator(0)` on all price fields; `MaxValueValidator(100)` on ABV; vintage max intentionally skipped (form-validated) |
| 12 | Standardize URL patterns across wine/whisky | ❌ Open | |
| 13 | Convert `.jsx` → `.tsx` in maps | ❌ Open | `Map.jsx`, `WineMaps.jsx` still `.jsx`; 1 `@ts-ignore` for `.jsx` import remains |
| 14 | Soft delete on Wine model | ❌ Open | |
| 15 | Integration/E2E tests with Playwright | ❌ Open | |
| 16 | Merge small JS bundles into `base.js` | ✅ Done | `wine_carousel` and `storage_view_toggle` merged into `base` entry |
| 17 | Add webpack-bundle-analyzer | ❌ Open | |
| 18 | Move storage URLs to proper app include | ✅ Done | `storage/urls.py` with `include()` in `conf/urls.py` |

**Progress: 10 of 18 complete** (56%)

---

## Executive Summary

The wine-cellar-personal project is a well-organized Django application with a React frontend. The core architecture is sound — clean app separation, good use of Django conventions, and a solid household multi-tenancy design.

**Top 5 priorities:**
1. ~~Massive code duplication between wine and whisky apps (~80% identical)~~ — still open
2. ~~Bundle sizes are bloated (maps.js is 6.9MB)~~ — ✅ mitigated by splitChunks (PR #58)
3. ~~Missing authorization enforcement on wine/whisky views~~ — ✅ resolved by `LoginRequiredMiddleware`
4. ~~N+1 query problems in model properties~~ — ✅ resolved by custom QuerySets
5. Business logic trapped in fat views instead of service layer — still open

---

## 1. Project Structure

### Strengths
- Clean Django app separation (core, wine, whisky, storage, household, user)
- Good config split (dev/prod/test/docker settings)
- Makefile provides clear developer workflow
- Docker + Raspberry Pi deployment is well thought out
- Pre-commit hooks (husky + lint-staged) enforce quality

### Issues

#### 1.1 Wine/Whisky Duplication (Critical) — ❌ Open

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

#### 1.2 Storage URLs at Root Level — ✅ Resolved

~~Storage routes are defined in `wine_cellar/conf/urls.py` rather than having their own `storage/urls.py` included via `include()`.~~

**Resolution:** Storage URL patterns extracted to `wine_cellar/apps/storage/urls.py` and included via `path("", include("wine_cellar.apps.storage.urls"))` in `conf/urls.py`.

#### 1.3 No Service Layer Convention — ❌ Open

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

#### 2.1 N+1 Query Problems in Properties — ✅ Resolved

~~Multiple Wine model properties trigger individual queries when accessed.~~

**Resolution:** Custom `WineQuerySet.with_related()` and `WhiskyQuerySet.with_related()` now provide `select_related`/`prefetch_related` optimization. Both use `HouseholdQuerySet` as a base class for tenant-scoped queries. `StorageItemQuerySet.in_stock()` and `WhiskyStorageItemQuerySet.in_stock()` also added.

> **Note:** The model *properties* (`get_vineyards`, `get_grapes`, etc.) still trigger individual queries when called without prefetch. The fix is at the QuerySet level — views must use `.with_related()` to benefit. Detail views already do this correctly.

#### 2.2 Missing Foreign Key Indexes (High)

Several frequently-queried FKs lack indexes:
- `WineImage.wine` — queried on every detail page
- `DrinkRecord.wine` — queried for consumption history
- `BottleNote.storage_item` — queried on bottle detail
- `WineBarcode.wine` — queried during barcode scans

Django auto-creates indexes on ForeignKey fields, but some older fields or fields with custom configurations may have been missed. Worth verifying with `SHOW INDEX` or Django's `inspectdb`.

#### 2.3 Custom Managers — ✅ Resolved

~~All models use Django's default manager.~~

**Resolution:** Custom querysets added:
- `WineQuerySet` with `with_related()` and `with_stock_count()`
- `WhiskyQuerySet` with `with_related()` and `with_stock_count()`
- `StorageItemQuerySet` with `in_stock()`
- `WhiskyStorageItemQuerySet` with `in_stock()`
- All inherit from `HouseholdQuerySet` for tenant-scoped filtering

#### 2.4 Cascade Deletion Destroys History (Medium) — ❌ Open

Deleting a Wine cascades to: DrinkRecord, PriceHistory, DrinkingWindowAlert, ReorderReminder, WineBarcode. This destroys valuable historical data.

**Recommendation:** Consider soft delete on Wine (like StorageItem), or archive patterns for historical records.

#### 2.5 Missing Validators — ✅ Resolved

~~`Wine.price` and `StorageItem.price` allow negative values; `Wine.abv` has no upper bound validator.~~

**Resolution:**
- `MinValueValidator(0)` added to `Wine.price`, `StorageItem.price`, `Whisky.price`, `WhiskyStorageItem.price`
- `MaxValueValidator(100)` added to `Wine.abv`
- `Wine.vintage` max validator intentionally removed (v0.0.2) — causes annual migrations; form-level validation handles this instead

#### 2.6 Inconsistent Naming (Low) — ❌ Open

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

#### 3.1 Auth Enforcement on Wine/Whisky Views — ✅ Resolved

~~Wine and whisky CBVs do not use `LoginRequiredMixin`.~~

**Resolution:** Since v0.0.2, the project uses `django.contrib.auth.middleware.LoginRequiredMiddleware` in the middleware stack, which enforces login on ALL views by default. Public views explicitly use `@login_not_required`. This is actually a stronger pattern than per-view `LoginRequiredMixin`. Tests confirm unauthenticated access redirects to login.

#### 3.2 Fat Views with Embedded Business Logic (High) — ❌ Open

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

#### 3.3 Transaction Safety — ✅ Resolved

~~`WineCreateView.process_form_data()` creates a Wine, then barcodes, then images, then M2M relationships across multiple database calls — without `@transaction.atomic`.~~

**Resolution:** Both `WineCreateView.process_form_data()` and `WineUpdateView.process_form_data()` now use `@staticmethod @transaction.atomic`. The wine merge operation also uses `with transaction.atomic():`.

> **Note:** Both `WhiskyCreateView.process_form_data()` and `WhiskyUpdateView.process_form_data()` now also use `@staticmethod @transaction.atomic`.

#### 3.4 Inconsistent Authorization Patterns (Medium) — ✅ Resolved

~~Wine and whisky views used manual `get_active_household()` per-method instead of the household mixin hierarchy.~~

**Resolution:** All wine and whisky CBVs now use `RequireHouseholdMixin` (read-only) or `RequireMemberMixin` (mutation). Inline `get_active_household()` calls remain in some methods (redundant but harmless) and will be cleaned up in future phases.

| App | Auth Pattern | Household Filtering |
|-----|-------------|-------------------|
| Household | Mixin hierarchy (excellent) | Enforced in mixin dispatch |
| Storage | Manual `get_active_household()` | Per-method, easy to forget |
| Wine | Mixin hierarchy | Enforced in mixin dispatch + some redundant per-method |
| Whisky | Mixin hierarchy | Enforced in mixin dispatch + some redundant per-method |

#### 3.5 Duplicated URL Patterns (Medium) — ❌ Open

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

#### 4.1 Coverage at 59% (Medium) — ❌ Open

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

#### 4.2 No Integration / E2E Tests (Medium) — ❌ Open

Tests are primarily unit-level. There are no tests for:
- Full create-wine-with-images flow
- Barcode scan → wine lookup → stock add flow
- Household invite → accept → shared data visibility

Playwright is installed but only used for manual UI checks, not automated test suites.

#### 4.3 Views.py Excluded from Coverage (Low) — ❌ Open

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

#### 5.1 Bundle Sizes — ✅ Mitigated

~~Maps alone were 13.7MB because Leaflet/MapLibre were duplicated across two bundles.~~

**Resolution:** PR #58 added `splitChunks` to `webpack.common.js` with dedicated cache groups for `react-vendors` and `leaflet-vendors`. This deduplicates React and Leaflet/MapLibre across all entry points.

> **Note:** Could be further improved with `webpack-bundle-analyzer` to measure actual savings and identify remaining duplication.

#### 5.2 TypeScript Safety Gaps — 🔄 Partially Resolved

**Resolved:**
- ✅ `types/django.d.ts` created with proper `declare module 'django'` type definitions
- ✅ Most `@ts-ignore` suppressions for Django imports removed

**Remaining:**
- ❌ 1 `@ts-ignore` remains in `react_maps.tsx` for `.jsx` import (`WineMaps`)
- ❌ ~10 `@ts-ignore` in `stock_add.ts` for TomSelect (needs `types/tom-select.d.ts`)
- ❌ 2 `@ts-ignore` in `react_bar_code.tsx` for zxing WASM
- ❌ Mixed `.jsx` / `.tsx` files in maps directory
- ❌ Vision extraction files (`.js`) not typed at all

#### 5.3 React Error Boundaries — ✅ Done

~~No error boundaries exist.~~

**Resolution:** Generic `ErrorBoundary` component created at `wine_cellar/react/components/ErrorBoundary.tsx` with retry functionality. Wraps all 5 React mount points:
1. Barcode scanner (`react_bar_code.tsx`)
2. Label scanner (`react_label_scanner.tsx`)
3. Storage grid (`storage_grid.tsx`)
4. Wine map (`react_maps.tsx`)
5. Distillery map (`react_distillery_map.tsx`)

#### 5.4 Small Bundles as Separate Entry Points (Low) — ✅ Resolved

~~`wine_carousel.js` (4KB) and `storage_view_toggle.js` (7KB) are separate HTTP requests for trivial functionality.~~

**Resolution:** Both scripts merged into the `base` webpack entry point. Both have lazy-init guards so they're safe to include on every page. Separate `<script>` tags removed from detail templates.

#### 5.5 No Production Source Maps (Low) — ❌ Open

`webpack.prod.js` sets `devtool: false`. Production errors will be impossible to debug without source maps.

---

## 6. Architecture Recommendations (Prioritized)

### Tier 1 — High Impact, Moderate Effort

| # | Issue | Effort | Impact | Status |
|---|-------|--------|--------|--------|
| 1 | Auth enforcement on all views | Small | Security | ✅ Done |
| 2 | `@transaction.atomic` on multi-model operations | Small | Data integrity | ✅ Done |
| 3 | Webpack `splitChunks` for vendor dedup | Small | 50% bundle reduction | ✅ Done |
| 4 | Custom QuerySet with `prefetch_related` | Medium | Eliminate N+1 queries | ✅ Done |
| 5 | Adopt household mixin pattern across all apps | Medium | Consistent authorization | ✅ Done |

### Tier 2 — High Impact, Higher Effort

| # | Issue | Effort | Impact | Status |
|---|-------|--------|--------|--------|
| 6 | Extract business logic from views to service layer | Large | Maintainability | ❌ Open |
| 7 | Extract shared wine/whisky code to abstract base | Large | Eliminate duplication | ❌ Open |
| 8 | Increase test coverage to 75%, include views.py | Medium | Reliability | ❌ Open |
| 9 | Create TypeScript definitions for Django integration | Small | Type safety | ✅ Done |
| 10 | Add React error boundaries | Small | User experience | ✅ Done |

### Tier 3 — Lower Priority

| # | Issue | Effort | Impact | Status |
|---|-------|--------|--------|--------|
| 11 | Add missing model validators (price, vintage) | Small | Data quality | ✅ Done |
| 12 | Standardize URL patterns across wine/whisky | Medium | Developer experience | ❌ Open |
| 13 | Convert .jsx to .tsx in maps components | Small | Type safety | ❌ Open |
| 14 | Soft delete on Wine model (preserve history) | Medium | Data preservation | ❌ Open |
| 15 | Add integration/E2E tests with Playwright | Large | Confidence | ❌ Open |
| 16 | Merge small JS bundles into base.js | Small | Fewer HTTP requests | ✅ Done |
| 17 | Add webpack-bundle-analyzer | Small | Visibility | ❌ Open |
| 18 | Move storage URLs to proper app include | Small | Convention | ✅ Done |

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
- **`LoginRequiredMiddleware`** — stronger than per-view mixins *(added since initial review)*
- **Custom QuerySets** with household scoping and prefetch optimization *(added since initial review)*
- **React ErrorBoundary** wrapping all mount points *(added since initial review)*
- **Webpack vendor chunking** deduplicates large libraries *(added since initial review)*