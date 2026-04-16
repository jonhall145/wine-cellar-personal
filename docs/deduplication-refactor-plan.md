# Deduplication Refactor Plan

## Overview

This plan describes a staged refactor to reduce duplicated code across the wine and whisky paths without changing user-facing behavior. The main target is repeated end-to-end feature logic where the same flow exists twice with small app-specific differences.

The highest-value work is concentrated in:

1. Create/scan/extraction flow
2. Stock item list/edit/add flow
3. Collection membership and collection API handling
4. Shared backend helpers for thumbnails, price/stock properties, and admin actions
5. Follow-up cleanup of small duplicated templates and module structure

---

## Goals

- Reduce copy-paste logic between wine and whisky features
- Keep behavior, URLs, templates, and API responses stable while refactoring
- Move duplication into shared base classes, helpers, and configurable templates
- Make future changes land once in shared code instead of twice in parallel files
- Split overly large modules where needed so shared code is easier to introduce safely

## Non-Goals

- Rewriting the app around a single polymorphic beverage model
- Changing user-visible terminology or navigation
- Large schema redesigns unrelated to duplication
- Mixing performance work into refactors unless required to preserve behavior

## Refactor Principles

- Prefer shared base classes and small configuration hooks over clever dynamic abstractions
- Consolidate complete feature slices before cleaning up tiny helpers
- Keep wine- and whisky-specific field mapping explicit at boundaries
- Refactor in small, reviewable phases with behavior checks after each phase
- Only centralize duplication that is already semantically aligned

---

## Priority Order

| Priority | Workstream | Why first |
|----------|------------|-----------|
| 1 | Create/scan/extraction flow | Largest repeated feature slice across templates, JS, and backend services |
| 2 | Stock item flows | Repeated filters, update logic, movement history, and templates |
| 3 | Collection flows and API | Repeated M2M handling in both HTML and API layers |
| 4 | Shared model/admin/command helpers | Easy wins once feature-level refactors settle |
| 5 | Small template cleanup and whisky module split | Useful cleanup, but lower leverage than the main flows |

---

## Phase 1: Consolidate Create/Scan/Extraction Flow

### Scope

- `wine_cellar/apps/wine/templates/wine_create.html`
- `wine_cellar/apps/whisky/templates/whisky/whisky_create.html`
- `wine_cellar/assets/js/vision_extraction.js`
- `wine_cellar/assets/js/whisky_vision_extraction.js`
- `wine_cellar/apps/wine/services/barcode_service.py`
- `wine_cellar/apps/whisky/services/barcode_service.py`
- `wine_cellar/apps/wine/services/vision_extraction.py`
- `wine_cellar/apps/whisky/services/vision_extraction.py`
- Shared entry points already in `wine_cellar/apps/core/views.py`

### Problems to Address

- Wine and whisky create pages are structurally the same with minor text and field differences.
- Vision extraction JavaScript duplicates request handling, field filling, confidence display, and error messaging.
- Barcode matching repeats the same variant lookup and result envelope shape.
- Claude vision service wrappers repeat API setup, image packing, response parsing flow, and extraction logging.

### Implementation Plan

1. Create a shared template such as `wine_cellar/templates/core/beverage_create.html`.
2. Keep app-specific values in context:
   - beverage label
   - scan/extract endpoint names
   - field-specific template includes if required
   - JS entrypoint/config
3. Replace both vision extraction JS files with a shared initializer that takes:
   - endpoint
   - beverage label
   - field map
   - confidence field map
   - any app-specific post-processing hooks
4. Introduce a shared barcode matching base in services with explicit hooks for:
   - beverage model
   - barcode model
   - related selects/prefetches
   - object-to-dict conversion
   - object-to-summary conversion
5. Introduce a shared vision extraction base that centralizes:
   - API key handling
   - image resizing pipeline
   - Claude request construction
   - success/error response envelope
   - extraction logging flow
6. Keep prompt text and field parsing in app-specific subclasses where the domain actually differs.

### Exit Criteria

- One shared create template powers both beverage creation pages
- One shared vision extraction JS module powers both scan flows
- Barcode lookup algorithm exists in one place
- Vision service request/response plumbing exists in one place
- Wine- and whisky-specific prompts and field parsing remain explicit and readable

---

## Phase 2: Consolidate Stock Item List/Edit/Add Flow

### Scope

- `wine_cellar/apps/storage/views.py`
- `wine_cellar/apps/whisky/views.py`
- `wine_cellar/apps/storage/filters.py`
- `wine_cellar/apps/whisky/filters.py`
- `wine_cellar/apps/storage/templates/stock_add.html`
- `wine_cellar/apps/whisky/templates/whisky/stock_add.html`
- Bottle list templates and filter integration where applicable

### Problems to Address

- List and update views repeat household lookup, storage loading, move detection, move-history writes, and success URL handling.
- Stock filters duplicate `show_used`, occasion filtering, storage queryset setup, and ordering structure.
- Stock add templates are almost identical.

### Implementation Plan

1. Add a shared stock filter base for common fields and methods:
   - storage
   - show used
   - has occasion
   - ordering skeleton
2. Add a shared storage item update base view that handles:
   - current object loading
   - free cell calculation
   - move detection
   - movement history creation hook
   - common field assignment
3. Keep whisky-only behavior as overrides:
   - fill level handling
   - dreg date transitions
   - owner-specific fields
4. Replace duplicated stock add templates with a shared template using context variables and small override blocks.
5. Recheck whether bottle list field rendering can rely more on the shared `core/beverage_list.html` path.

### Exit Criteria

- Shared base filter handles common stock filtering behavior
- Shared base update view handles move/save boilerplate
- Shared stock add template replaces both duplicated templates
- Whisky-specific stock behavior remains isolated to small overrides

---

## Phase 3: Consolidate Collection Membership and Collection API Handling

### Scope

- `wine_cellar/apps/wine/views/wine_crud.py`
- `wine_cellar/apps/whisky/views.py`
- `wine_cellar/apps/api/viewsets/wine.py`
- `wine_cellar/apps/api/viewsets/whisky.py`
- `wine_cellar/apps/api/serializers/wine.py`
- `wine_cellar/apps/api/serializers/whisky.py`

### Problems to Address

- Add/remove collection handlers are nearly identical.
- Collection viewsets duplicate read/write serializer switching and prefetch behavior.
- Collection serializers duplicate M2M syncing patterns.

### Implementation Plan

1. Extract HTML collection membership handling into a shared helper or mixin with configurable:
   - beverage model
   - collection model
   - relation name (`wines` / `whiskies`)
   - detail route name
2. Extract collection serializer M2M syncing into a shared serializer base.
3. Extract collection viewset read/write serializer switching into a shared mixin.
4. Consider a small shared helper for API-key household queryset scoping in write serializers where the current logic repeats.

### Exit Criteria

- Collection add/remove flow exists once for HTML views
- Collection read/write serializer behavior exists once
- Collection viewset behavior exists once

---

## Phase 4: Consolidate Shared Backend Helpers

### Scope

- `wine_cellar/apps/wine/models.py`
- `wine_cellar/apps/whisky/models.py`
- `wine_cellar/apps/wine/admin.py`
- `wine_cellar/apps/whisky/admin.py`
- `wine_cellar/apps/wine/management/commands/regenerate_thumbnails.py`
- `wine_cellar/apps/whisky/management/commands/regenerate_thumbnails.py`
- `wine_cellar/apps/wine/signals.py`
- `wine_cellar/apps/whisky/signals.py`
- `wine_cellar/apps/core/models.py`
- `wine_cellar/apps/core/admin.py`

### Problems to Address

- Price formatting helpers are duplicated.
- Stock helper properties are duplicated.
- Soft-delete restore admin actions are duplicated.
- Thumbnail regeneration commands are duplicated.
- Thumbnail save signals are duplicated.

### Implementation Plan

1. Introduce a shared mixin for price formatting and average-price formatting with explicit relation-name configuration.
2. Introduce a shared mixin for stock helper properties.
3. Add a shared admin mixin for restoring soft-deleted records.
4. Add a shared thumbnail regeneration command base.
5. Add a shared thumbnail generation signal helper where the only variable is the image model.
6. Remove any stray duplicated helper definitions already centralized elsewhere.

### Exit Criteria

- Price and stock helpers are shared mixins
- Restore action is implemented once
- Thumbnail regeneration command flow is implemented once
- Thumbnail save helper logic is implemented once

---

## Phase 5: Cleanup, Convergence, and Smaller Duplicates

### Scope

- `wine_cellar/apps/whisky/views.py`
- `wine_cellar/apps/wine/templates/wine_filter_field.html`
- `wine_cellar/apps/whisky/templates/whisky/whisky_filter_field.html`
- Wishlist header/row include fragments
- Homepage alert fragments
- Reorder reminder confirmation templates

### Problems to Address

- `apps/whisky/views.py` is still a monolith, while wine views are already split by feature.
- Several small templates are identical or near-identical.
- Some duplication is minor individually but still adds friction to layout or copy changes.

### Implementation Plan

1. Split `apps/whisky/views.py` into feature modules mirroring the wine structure:
   - CRUD
   - drink
   - wishlist
   - scan
   - reminders
   - home
2. Replace fully identical partials with one shared partial.
3. Replace small include pairs with context-driven rendering where the table or widget structure is already shared.
4. Leave template forks in place only when the domain difference is meaningful and likely to diverge further.

### Exit Criteria

- Whisky views are organized similarly to wine views
- Identical template partials are unified
- Tiny include duplication is reduced without making templates harder to read

---

## Validation Strategy

Each phase should be merged independently and validated before starting the next. Validation should focus on preserving behavior rather than proving the abstraction itself.

### Minimum checks per phase

- Relevant pytest coverage for affected views/forms/services
- Relevant lint targets
- Manual spot checks for:
  - wine create flow
  - whisky create flow
  - stock add/edit flow
  - collection add/remove flow
  - scan/extract flow

### Regression-sensitive areas

- Scan form field population and confidence badges
- Barcode match envelopes returned to AJAX callers
- Storage movement history creation
- Whisky fill-level and dreg-date transitions
- Collection serializer write behavior
- Template context variable completeness

---

## Risks and Mitigations

| Risk | Why it matters | Mitigation |
|------|----------------|------------|
| Over-abstraction | Shared code becomes harder to follow than duplicated code | Use base classes plus explicit config, not deep generic metaprogramming |
| Silent behavior drift | Wine and whisky differ in subtle field handling | Keep field mapping, prompts, and domain parsing app-specific |
| Template context breakage | Shared templates depend on complete context wiring | Add refactor phase checks for all affected routes |
| Large PRs | Harder to review and rollback | Land one phase at a time |
| Monolith interference in whisky views | Hard to extract shared code cleanly | Split modules before or during Phase 5 |

---

## Suggested Delivery Sequence

1. Shared create template + shared vision extraction JS
2. Shared barcode service base
3. Shared vision extraction service base
4. Shared stock add template
5. Shared stock filter/update base
6. Shared collection HTML helpers
7. Shared collection serializer/viewset mixins
8. Shared thumbnail/admin/model helper mixins
9. Whisky view module split
10. Small partial/template cleanup

---

## Definition of Done

This deduplication effort is complete when:

- The create/scan/extract flow has one shared implementation path for common behavior
- Stock item filtering/editing boilerplate is shared
- Collection membership logic is shared in both HTML and API layers
- Repeated backend helpers are expressed as shared mixins or command bases
- Identical template partials are removed
- Wine and whisky behavior still differ only where the domain truly differs
- The codebase is easier to extend without copying changes across parallel files
