# Changelog

All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.3.6 (2026-04-12)


## 0.3.5 (2026-03-29)


## 0.3.4 (2026-03-24)

### fix

- iOS PWA install banner with iPadOS 13+ and Chrome detection (#154)
    
    * ci: always PR to next branch
    
    * fix: ios pwa install banner with ipadOS 13+ and chrome detection
    
    * fix: address pr review comments on ios install banner
    
    * fix: tighten iOS install banner / update-banner coordination (#155)
    
    * Initial plan
    
    * fix: improve install banner/update-banner coordination per review feedback
    
    Co-authored-by: jonhall145 <105321987+jonhall145@users.noreply.github.com>
    Agent-Logs-Url: https://github.com/jonhall145/wine-cellar-personal/sessions/7237621d-17dd-469b-ae6c-d6db821b6451
    
    ---------
    
    Co-authored-by: copilot-swe-agent[bot] <198982749+Copilot@users.noreply.github.com>
    Co-authored-by: jonhall145 <105321987+jonhall145@users.noreply.github.com>
    
    ---------
    
    Co-authored-by: jonhall145 <jonhall145@users.noreply.github.com>
    Co-authored-by: Copilot <198982749+Copilot@users.noreply.github.com>



## 0.3.3 (2026-03-22)

### feat

- add REST API with DRF, API key auth, and move history tracking

- full REST API with DRF and API key auth (#160)
    
    * feat: add full REST API with DRF and API key auth (closes #100)
    
    * fix: address pr review comments
    
    - scope write serializer FK/M2M querysets to household (prevent cross-household refs)
    
    - add missing prefetch_related for barcodes, cask_history, and collection nested data
    
    - strip whitespace from auth token
    
    - rate-limit last_used updates (5min threshold)
    
    - set finished_date on soft-delete of storage items
    
    - remove unused PAGE_SIZE from REST_FRAMEWORK config
    
    * fix: address PR review - bugs, filtering, tests, slim serializers
    
    - remove stray class Meta from WineViewSet
    - fix N+1 on StorageSerializer (split list/detail)
    - fix BottleMoveHistorySerializer to exclude user field
    - require --all flag on revoke_api_key for multiple matches
    - simplify create_api_key date parsing, remove unused import
    - add django-filter backend with filtering/search/ordering on wines and whiskies
    - use slim summary serializers for collection membership
    - add 14 new tests: whisky CRUD, storage item CRUD, FK scoping, pagination, global refs, revoke --all
    
    * fix: use objects.none() as default queryset on all write serializers
    
    Defense-in-depth: if request context is missing, FK/M2M querysets
    default to empty rather than allowing all objects. Addresses Copilot
    review comments about cross-household reference prevention.
    
    ---------
    
    Co-authored-by: jonhall145 <jonhall145@users.noreply.github.com>

- add full REST API with DRF and API key auth (closes #100)

- add owner filter to whisky bottles and whisky list (#157) (#159)
    
    * feat: add owner filter to whisky bottles and whisky list (closes #157)
    
    * fix: only show owner filter when owner values exist
    
    * fix: address pr review comments
    
    - fix show_used filter: use explicit '0' value with injected default so deleted bottles are correctly excluded without query params
    - add RequireHouseholdMixin to StorageItemListView, BottleHistoryView, WhiskyBottleHistoryView
    - fix finished_date to use date_consumed from form instead of date.today()
    - add tests for show_used default/explicit and owner filter
    
    ---------
    
    Co-authored-by: jonhall145 <jonhall145@users.noreply.github.com>

- bottle tracking history (#156) (#158)
    
    * feat: add bottle tracking history (issue #156)
    
    - Add finished_date to StorageItem and WhiskyStorageItem
    - Add BottleMoveHistory and WhiskyBottleMoveHistory models to track storage moves
    - Set finished_date when bottles are deleted or consumed
    - Fix whisky StorageItemDeleteView hard-delete bug (was not soft-deleting)
    - Record move history when bottle position changes in StorageItemUpdateView
    - Add BottleHistoryView and WhiskyBottleHistoryView with timeline of events
    - New bottle_history.html template showing added/move/drink/opened/dreg/finished
    - Add history button to wine_detail, whisky_detail, and both bottle_list tables
    - Add show_used filter to bottle list filtersets (default: in-stock only)
    
    * fix: isort import formatting in whisky views
    
    * fix: hide edit/remove buttons for finished bottles in list view
    
    * fix: flake8 line length and formatting
    
    ---------
    
    Co-authored-by: jonhall145 <jonhall145@users.noreply.github.com>


### fix

- remove blurry scroll hint gradient from grid view (#163) (#164)
    
    Co-authored-by: jonhall145 <jonhall145@users.noreply.github.com>

- address review round 2 - app_type filtering, validation, race conditions

- address PR review - transactions, validation, date parsing, tests

- record move history when moving bottles via grid view and API

- use objects.none() as default queryset on all write serializers
    
    Defense-in-depth: if request context is missing, FK/M2M querysets
    default to empty rather than allowing all objects. Addresses Copilot
    review comments about cross-household reference prevention.

- address PR review - bugs, filtering, tests, slim serializers
    
    - remove stray class Meta from WineViewSet
    - fix N+1 on StorageSerializer (split list/detail)
    - fix BottleMoveHistorySerializer to exclude user field
    - require --all flag on revoke_api_key for multiple matches
    - simplify create_api_key date parsing, remove unused import
    - add django-filter backend with filtering/search/ordering on wines and whiskies
    - use slim summary serializers for collection membership
    - add 14 new tests: whisky CRUD, storage item CRUD, FK scoping, pagination, global refs, revoke --all

- address pr review comments
    
    - scope write serializer FK/M2M querysets to household (prevent cross-household refs)
    
    - add missing prefetch_related for barcodes, cask_history, and collection nested data
    
    - strip whitespace from auth token
    
    - rate-limit last_used updates (5min threshold)
    
    - set finished_date on soft-delete of storage items
    
    - remove unused PAGE_SIZE from REST_FRAMEWORK config

- tighten iOS install banner / update-banner coordination (#155)
    
    * Initial plan
    
    * fix: improve install banner/update-banner coordination per review feedback
    
    Co-authored-by: jonhall145 <105321987+jonhall145@users.noreply.github.com>
    Agent-Logs-Url: https://github.com/jonhall145/wine-cellar-personal/sessions/7237621d-17dd-469b-ae6c-d6db821b6451
    
    ---------
    
    Co-authored-by: copilot-swe-agent[bot] <198982749+Copilot@users.noreply.github.com>
    Co-authored-by: jonhall145 <105321987+jonhall145@users.noreply.github.com>

- address pr review comments on ios install banner

- ios pwa install banner with ipadOS 13+ and chrome detection



## 0.3.2 (2026-03-21)

### fix

- persist target storage selection in move mode (#152)



## 0.3.1 (2026-03-21)

### fix

- remove missing changelog_start_rev from commitizen config



## 0.3.0 (2026-03-21)

### feat

- allow multi-select wine type and grape filters (#153)
    
    * feat: allow multi-select wine type and grape filters (closes #150)
    
    * fix: handle single vs multi wine_type in _post_clean
    
    ---------
    
    Co-authored-by: jonhall145 <jonhall145@users.noreply.github.com>

- iOS Add to Home Screen hint in nav menu

- add iOS Add to Home Screen hint in nav menu

- full-text search across notes and descriptions

- full-text search across notes and descriptions
    
    Add a search filter to both wine and whisky list pages that searches across name, comment, subregion, tasting notes (from drink records), and bottle notes. Replaces the name-only filter with a broader search field.
    
    Closes #118
    
    Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

- add robust app versioning system

- add robust app versioning system
    
    - Version bump script (scripts/bump_version.py) updates __init__.py + pyproject.toml
    - Make targets: bump-patch/minor/major, version, changelog, release
    - Public /api/version/ endpoint returning version, app_type, git_sha
    - PWA: controlled update flow with user-prompted banner instead of auto-skipWaiting
    - Version field added to manifest.json
    - SW registration moved from inline script to bundled TypeScript
    - Tests for version API, manifest version, and SW update flow
    
    Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

- vision extraction refinements

- vision extraction refinements (#109)
    
    - per-field confidence indicators (green/yellow/red dots next to fields)
    - fuzzy appellation matching with difflib SequenceMatcher
    - batch scanning via Save & Scan Another button
    - track user corrections in extraction logs
    - show extraction history on wine/whisky detail pages
    - fix black target-version warning

- implement low-complexity github issues #94, #96, #98, #113, #114, #115
    
    - #96: add webpack-bundle-analyzer with npm run analyze script
    - #113: bottle count badge in nav bar via context processor
    - #114: random bottle picker with homepage button
    - #115: QR code generation for wine/whisky detail pages
    - #98: recently viewed beverages on homepage (session-based)
    - #94: convert map .jsx components to .tsx with TypeScript types

- add filters, storage management, vision logging, and UI improvements
    
    Phase 1 - Quick Fixes:
    - Add "Has Window" option to ready to drink filter (wines with drink_from/drink_to set)
    - Fix wine count on filtered views by adding .distinct()
    - Create drink_record_edit.html template for editing drink history
    - Remove Hardware settings section from sidebar
    - Optimize map bundle by lazy-loading country.json and removing unused country_points.json
    
    Phase 2 - Mobile/UI:
    - Fix More dropdown menu on mobile with touch-friendly click handler
    - Add mobile touch targets (44px min-height) for form elements
    
    Phase 3 - Database Changes:
    - Add cold storage filter with is_cold field on Storage model
    - Add storage reordering with order field and move up/down endpoints
    - Add is_default field to mark default storage per user
    - Create VisionExtractionLog model for tracking vision extractions
    - Add analyze_extractions management command for extraction analytics
    
    Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- add clickable wine names in grid and bottle selection for drink records
    
    This commit implements two related features to improve wine tracking and navigation:
    
    1. Clickable Wine Titles in Storage Grid
       - Wine names in grid tooltips are now clickable links
       - Clicking navigates to wine detail page
       - Does not interfere with drag-and-drop functionality
       - Works on both desktop and mobile
    
    2. Bottle Selection for Drink Records
       - Added storage_item FK field to DrinkRecord model
       - Users can now select which specific bottle they consumed
       - Dropdown shows available bottles with storage locations
       - Selected bottles are automatically marked as deleted
       - Stock count decreases automatically
       - Bottle selection is optional
    
    Backend Changes:
    - wine_cellar/apps/wine/models.py: Add storage_item field to DrinkRecord
    - wine_cellar/apps/storage/models.py: Add __str__() method for display
    - wine_cellar/apps/wine/forms.py: Add bottle selection field with validation
    - wine_cellar/apps/wine/views.py: Handle bottle deletion on drink record
    - wine_cellar/apps/wine/templates/drink_record_create.html: Add bottle field
    - Migration 0027: Add storage_item field to DrinkRecord table
    
    Frontend Changes:
    - wine_cellar/react/storage_grid.tsx: Make wine name clickable in tooltip
    - wine_cellar/assets/css/storage.css: Add link styling with hover effects
    
    Tests:
    - tests/test_views.py: Add 3 comprehensive unit tests for bottle selection
    - All 28 tests pass successfully
    
    Documentation:
    - docs/models.md: Update DrinkRecord and StorageItem documentation
    - docs/storage.md: Document clickable wine names in grid view
    - docs/wine.md: Document drink record bottle selection feature
    
    Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- enhance HTTPS scripts with meshnet support
    
    Improve run_https.sh:
    - Auto-detect meshnet IP addresses (100.64.0.0/10 range)
    - Generate SSL certificates with comprehensive Subject Alternative Names
    - Include localhost, LAN IP, and meshnet IP in certificate
    - Improve console output to show all available access URLs
    
    Improve run_prod_https.sh:
    - Use $ENV_FILE variable instead of hardcoded .env.prod.local path
    - Allows for more flexible environment configuration
    
    Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- Enhance filters, country extraction, and add gift/occasion fields
    
    - Add "Any" option to Ready to Drink and Rating filters for better UX
    - Change Rating filter from minimum (1+, 2+, 3) to exact match (0, 1, 2, 3)
    - Improve country extraction with region-to-country and appellation mappings
    - Add comprehensive wine region database covering 15+ countries
    - Enhance Claude Vision prompt with specific country detection strategies
    - Add gift metadata fields (is_gift, gift_from, occasion) to wine creation form
    
    Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- Country filter shows only stocked countries + scan order change
    
    - Country dropdown now only shows countries with wines in stock
    - Scan order changed to: barcode → back label → front label
      (reduces bottle turning since barcode is on back)
    - Updated backend image indices to match new scan order
    
    Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- Replace drink_by date with drink_from/drink_to year-based drinking window
    
    Major changes:
    - Migrate from single drink_by date to drink_from/drink_to year fields
    - Update drinking window alerts and reminders to use new fields
    - Auto-attach scanned label images when creating wines
    - Add deployment script and documentation
    - Fix security: return 404 when accessing other user's wines
    - UI improvements for bottle list and storage grid
    
    Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- Add rating and ready-to-drink filters to wine list
    
    Add two new filtering options to help users find wines:
    - Minimum rating filter (1+, 2+, or 3 stars)
    - Ready to drink filter based on drinking window (drink_from/drink_to years)
    
    Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- Add star rating widget to bottle edit page and display rating on grid thumbnails
    
    - Added StarRatingWidget class for interactive star selection (0-3 stars)
    - Updated StorageItemEditForm to use star rating widget instead of plain number input
    - Added rating to storage grid API response (bottle rating with wine fallback)
    - Display star ratings below bottle icons on grid view
    - Added CSS styling for rating stars on grid cells

- add pre-commit config and custom error pages
    
    Add .pre-commit-config.yaml with Python linting hooks (black, isort,
    flake8, djlint) for developers not using npm/Husky.
    
    Add custom error pages (400, 403, 404, 500) with styled templates
    and helpful user messages.
    
    Update TODO.md to mark completed items (#8, #9).
    
    Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- add rate limiting for authentication and wine creation
    
    Add ACCOUNT_RATE_LIMITS for login/signup/password reset (5/min/ip).
    Add rate limiting to WineCreateView (20/min/user).
    Update TODO.md to mark completed items (#1, #3, #4, #6, #10, #18, #19, #34).
    
    Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- enhance health check endpoint and remove FAB component
    
    Improve /health/ endpoint to check database, disk space, and Celery status.
    Remove mobile floating action button (FAB) from UI - the bottom navigation
    provides equivalent quick access to scan and add wine actions.
    
    Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- add structured logging configuration
    
    - Configure Django logging with verbose formatter
    - Add wine_cellar and wine_cellar.audit loggers
    - Support LOG_LEVEL environment variable
    - Email admins on errors in production
    - Update prod.py and test.py with logging exports
    - Document LOG_LEVEL in environment.md
    
    Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- **security**: add rate limiting and fix wildcard imports    
    - Add django-ratelimit dependency for API protection
    - Rate limit vision extraction endpoint (10 req/min per user)
    - Rate limit barcode scan endpoint (30 req/min per user)
    - Replace wildcard imports in prod.py with explicit imports
    - Replace wildcard imports in test.py with explicit imports
    - Enable production security settings (HSTS, SSL redirect, secure cookies)
    
    Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- Interactive storage grid view with drag-and-drop
    
    ## Features
    - Visual grid display of wine racks with bottles shown as icons
    - Mouseover/tap tooltips showing wine name, vintage, type, country
    - Drag-and-drop to move bottles within a rack
    - Move bottles between different wine racks via dropdown
    - Toggle between list view and grid view
    - Real-time updates after moving bottles
    
    ## Technical Details
    - New React component: storage_grid.tsx
    - API endpoints: /api/storage/grid-data/ and /api/storage/move-bottle/
    - CSS styling with dark theme support
    - Webpack entry for storage_grid.js
    
    ## UI/UX
    - Grid cells colored wine-red when occupied
    - Visual feedback during drag operations
    - Success/error messages for move operations
    - Instructions shown for user guidance

- AJAX vision extraction without page reload
    
    - Add extract_wine_vision_ajax endpoint for AJAX processing
    - Create vision_extraction.js for client-side handling
    - Auto-fill form fields in real-time without page reload
    - Show success/error messages inline
    - Change button to type='button' to prevent form submission
    - Loading spinner during extraction
    - Users can now upload images and trigger extraction seamlessly

- Multi-image vision extraction with Claude 4.5
    
    - Update vision extraction to support multiple images (barcode, front label, back label)
    - Add extract_from_images() method to process all images at once for better accuracy
    - Update Claude API model to claude-sonnet-4-5 (from deprecated 3.5)
    - Add cache mechanism to prevent re-processing images on page reload
    - Implement multi-step camera capture flow (1/3, 2/3, 3/3)
    - Add 'Auto-fill from Images' button in wine creation form
    - Add file upload option in label scan page
    - Update both HTTPS server scripts to default to port 8000
    - Vision prompt now instructs Claude to combine info from ALL images

- add AI-powered vision-based wine label extraction
    
    Implement comprehensive zero-typing wine entry using Claude Vision API:
    
    **Core Features:**
    - WineVisionExtractor service for AI-powered label analysis
    - Automatic extraction of wine data (name, type, vintage, ABV, grapes, etc.)
    - Intelligent field mapping and validation
    - Confidence scoring (high/medium/low)
    - Fallback regex extraction when API unavailable
    
    **UI Enhancements:**
    - Scanned label preview with confidence badges
    - Auto-filled form fields with visual indicators
    - Re-scan functionality
    - Error handling and user feedback
    
    **Configuration:**
    - Add anthropic==0.40.0 dependency
    - ANTHROPIC_API_KEY environment variable
    - Settings integration for API key
    
    **Documentation:**
    - Comprehensive vision-wine-entry.md guide
    - Setup instructions
    - Troubleshooting section
    - Privacy and security notes
    - Cost analysis (~$2-3/year for personal use)
    
    **Session Management:**
    - Store scanned image and extraction results in session
    - Clear session data after successful wine creation
    - Graceful error handling
    
    Enables users to add wine without typing by simply photographing the label.

- **stats**: if a stock item has no price, use the price of the wine
- **wine**: add sorting by average price and total value statistic    
    - the wine list can now be sorted by the average price of a wine
    - the homepage shows the total value of all bottles in stock

- **stock**: add option to add the bottle price to a stock item    
    - show average price across all bottles of a wine in wine detail view

- **wine**: allow uploading multiple images of a wine    
    This allows uploading images for front, back, label front, label back.
    Additionally, previews are now shown in the form and images can be
    deleted.

- **auth**: use django-allauth for authentication    
    For now this will allow login via openid_connect. Other providers can be
    added on request. Also adds proper email and password change views.
    
    It also introduces a new setting `ENABLE_SIGNUP` which defaults to `False`.
    To enable signups add/change it in `.env-prod`.

- **storage**: add a stock history page which lists removed stock items    
    mark stock items as deleted instead of actually deleting them from the db

- **wine**: add orange wine to model with migration

### fix

- capitalise APP_ITEM_NAME in headings (closes #146) (#148)
    
    Co-authored-by: jonhall145 <jonhall145@users.noreply.github.com>

- use TomSelect sync() to rebuild options on iOS
    
    Replace the manual clearOptions()+addOption() loop with
    clear()+clearOptions()+sync() so TomSelect's internal caches
    (options map, sifter index, rendered items) are fully rebuilt
    from the native select when row/column options change after a
    storage selection.
    
    Fixes #143 - rows dropdown not working on iPhone.

- auto-select first row/column in TomSelect after storage selection

- auto-select first row/column in TomSelect after storage selection
    
    On iOS, TomSelect's dropdown won't open if the control shows no selected
    value. Previously populateSelect() populated TomSelect options but never
    called setValue(), leaving the control visually empty even though the
    native select had the first option selected by default.
    
    Fix: pass the native $option DOM reference in addOption() so setValue()
    can link to the existing element without creating duplicate native options,
    then auto-select the first option when no restoreValue is given.

- auto-select first row/column in TomSelect after storage selection
    
    On iOS, TomSelect's dropdown won't open if the control shows no selected
    value. Previously populateSelect() populated TomSelect options but never
    called setValue(), leaving the control visually empty even though the
    native select had the first option selected by default.
    
    Fix: pass the native $option DOM reference in addOption() so setValue()
    can link to the existing element without creating duplicate native options,
    then auto-select the first option when no restoreValue is given.

- per_page selector now preserves current path

- per_page selector now preserves current path

- add appellations fixture to Dockerfile.rpi4
    
    The GHCR deploy uses Dockerfile.rpi4, not Dockerfile. Add appellations.json to the COPY line so it's available in the production image.
    
    Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

- load appellations fixture on production deploy
    
    Add appellations.json to Docker image COPY and docker-entrypoint.sh loaddata so appellations (including Surrey) are available in production.
    
    Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

- gitignore venv symlink
    
    Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

- wrap long docstring to satisfy flake8 line length
    
    Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

- remove venv symlink accidentally committed
    
    Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

- address PR review comments
    
    Reword filter_search docstring to say 'keyword search' instead of 'full-text search'. Rename test_wine_list_name_filter to test_wine_list_search_filter.
    
    Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

- address PR review comments
    
    - build update banner with createElement/textContent instead of innerHTML
    - always attach updatefound listener, guard against duplicate banners
    - resolve git SHA once at module import, not per request; use explicit cwd
    - --tag now commits version files before creating the tag
    - validate TOML regex match before writing to pyproject.toml
    
    Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

- copy extracted_data before resolve to avoid session serialization error

- media volume permissions - run entrypoint as root, drop to django via gosu

- e2e per_page test - use expect_navigation to wait for page load

- e2e per_page test - don't use stock=1 filter (no storage items in fixture)

- override STORAGES in conftest so tests don't need collectstatic

- per_page selector now preserves current path

- address PR review comments
    
    - handle IntegrityError in admin restore actions (restore one-by-one, skip conflicts)
    - filter deleted=False in BaseBeverageDeleteView.get_queryset
    - exclude soft-deleted beverages from homepage storage aggregates (total_value, bottles_in_stock)

- address soft delete review issues
    
    - use partial unique constraint (condition=Q(deleted=False)) instead of adding deleted to constraint fields, allowing multiple soft-deleted records per natural key
    - add deleted=False to get_or_create in wine_crud and whisky create views
    - add deleted=False to country filter queries in core/filters.py
    - add deleted=False to get_related_model_choices_cached filter
    - add audit logging to bulk delete via log_delete
    - add deleted field, list_filter, and restore action to wine and whisky admin
    - add wine soft delete unit tests (test_wine_soft_delete, test_soft_deleted_wine_hidden_from_list)
    - update e2e delete test to verify soft delete behavior

- prevent migration failures on deploy
    
    - add post-migrate verification to entrypoint that retries if unapplied migrations remain
    - add --force-recreate to wine-deploy and whisky-deploy targets

- address review - import order, CSS variables, milestone query for all bottles

- add currency formatting, date formatting, event limit, and query optimization to journey timeline

- skip e2e tests when playwright browsers missing, add zero-tolerance test policy to CLAUDE.md

- add login_required to collection views, add ordering to wine Collection, deduplicate get_collection_choices

- escape JS labels, clean up select_related, fix distillery test
    
    - Add |escapejs filter to all Chart.js label interpolations (XSS fix)
    - Move 'storage' into initial select_related instead of redundant call
    - Simplify sum(v for v in ...) to sum(...)
    - Fix test using wrong context key (by_distillery -> by_group)
    - Restore unrelated test-results files deleted by previous commit
    - Fix line-too-long lint issues

- use specific button selector in e2e test for save_finish

- remove conflicting COMPOSE_IGNORE_ORPHANS with --remove-orphans

- regenerate lock file after barcode-detector revert

- line too long in wine duplicate test

- correct import sort order and line length in wine urls

- address review issues on duplicate detection PR
    
    - remove unreachable auth check in check_beverage_duplicate_ajax
    
    - replace invalid <meta> in body with data-* attribute on hidden input
    
    - add rate limiting (60/m) to both duplicate check endpoints
    
    - move import to top-level in whisky views for consistency
    
    - escape URL in JS href for defensive XSS prevention

- use correct HouseholdRole code OW instead of owner in e2e fixture
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- add debug assertions to e2e crud tests for CI diagnosis
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- scope e2e crud selectors to form, fix submit button name
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- use correct wine_type codes and selectors in e2e tests
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- rewrite e2e tests with correct URLs, selectors, and active household
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- allow async-unsafe ORM calls in playwright e2e tests
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- bump pytest-playwright to 0.7.2 for pytest 9 compatibility
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- address PR review comments
    
    - Cache wines.count() to avoid duplicate DB query in drink reminders
    - Use self.object instead of self.get_object() in delete audit log
    - Pin Chart.js to 4.4.8 with SRI integrity hash
    - Make sentry_sdk import conditional inside SENTRY_DSN check
    - Remove hardcoded repo URL and clarify test credentials in CONTRIBUTING.md
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- override serialize-javascript to 7.0.3 for RCE vulnerability

- override serialize-javascript to 7.0.3 for RCE vulnerability
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- address PR review comments
    
    - Use StorageItem.objects.none() instead of queryset=None on ModelChoiceField
    - Change BaseWishlistPurchasedView from GET to POST with RequireMemberMixin
    - Pass wine=item whisky=item to card templates in scanned_beverage.html
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- filter null markers before length check and rendering
    
    Co-authored-by: jonhall145 <105321987+jonhall145@users.noreply.github.com>

- load leaflet-vendors.css on map pages

- load leaflet-vendors.css on map pages
    
    The webpack leafletVendor splitChunks config extracts Leaflet, MaplibreGL,
    and MarkerCluster CSS into leaflet-vendors.css, but the map templates only
    loaded maps.css (which only has custom styles). Without the vendor CSS:
    - No z-index on leaflet panes, so markers render behind the GL canvas
    - No touch-action:none, so mobile touch scrolls the page instead of panning
    - No maplibre-gl sizing rules, so the map doesn't fill its container
    
    Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

- load leaflet-vendors.css on wine and whisky map pages

- load leaflet-vendors.css on map pages
    
    The webpack leafletVendor splitChunks config extracts Leaflet, MaplibreGL,
    and MarkerCluster CSS into leaflet-vendors.css, but the map templates only
    loaded maps.css (which only has custom styles). Without the vendor CSS:
    - No z-index on leaflet panes, so markers render behind the GL canvas
    - No touch-action:none, so mobile touch scrolls the page instead of panning
    - No maplibre-gl sizing rules, so the map doesn't fill its container
    
    Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

- bundle country.json into map JS to fix missing wine markers

- bundle country.json into map JS instead of runtime fetch
    
    The runtime fetch('/static/maps/country.json') was failing in production,
    causing the map to render tiles but never display wine markers. Import
    the JSON directly via webpack so it's always available.
    
    Also fixes the null-check bug where Object.assign({}, undefined) returns
    {} (truthy), so wines with missing country codes were never filtered out.
    
    Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

- load react-vendors.js on wine and whisky map pages

- load react-vendors.js on wine and whisky map pages
    
    The react-vendors splitChunks group (added in ee27945) extracts React
    and ReactDOM into a separate chunk, but wine_map.html and whisky_map.html
    were never updated to load it. Without react-vendors.js the map React
    components have no React at runtime and silently fail to render.
    
    Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

- TomSelectMixin empty list bug; add 32 core tests
    
    - Fix set_tom_config: 'if items is not None' -> 'if items' to preserve
      original behavior where empty lists are excluded from config
    - Add tests for TomSelectMixin, BottleNoteForm, ReorderReminderForm
    - Add tests for rating_stars and badge template tags
    - Add tests for base64_to_uploaded_file utility
    - Add integration tests for wishlist, drink record, bottle note,
      reorder reminder, and cellar value views
    - Verify household scoping on delete views
    
    Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

- test media permissions in Docker and duplicate dict key
    
    - Use tempfile for MEDIA_ROOT in test settings so the non-root Docker
      user can write test images
    - Update clear_image_folder fixture to use settings.MEDIA_ROOT
    - Remove duplicate châteauneuf key in vision_extraction.py
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- force-recreate all services on ghcr-deploy
    
    Recreates the full stack (including db and redis) from the GHCR image
    while preserving named volumes (postgres_data, redis_data, etc.).
    
    Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- run single compose up in ghcr-deploy to avoid orphan warnings
    
    Running multiple up commands each targeting a subset of services caused
    Docker Compose to warn about the rest as orphans. A single up --no-build
    manages all services together; Compose detects the retagged wine-cellar:prod
    image and recreates only wine-web and whisky-web automatically.
    
    Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- ensure db and redis are running before ghcr-deploy
    
    Previously --no-deps skipped db/redis entirely. Now they are brought
    up first (no-op if already running) before recreating the web containers.
    
    Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- suppress orphan container warning in ghcr-deploy
    
    db and redis are managed separately; COMPOSE_IGNORE_ORPHANS=1 tells
    Docker Compose they are intentional so the warning is suppressed.
    
    Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- use whisky price as fallback on cellar value page

- shorten docstrings to pass flake8 line length check
    
    Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- use explicit None checks for price fallback on cellar value pages

- use explicit None checks for price fallback on cellar value pages
    
    Replace Python `or` operator (which treats Decimal("0.00") as falsy)
    with explicit `is not None` checks when computing per-distillery/
    per-type/per-country item prices on the cellar value page, for both
    whisky and wine apps.
    
    Also adds tests verifying:
    - whisky/wine.price is used when storage_item.price is NULL
    - A storage_item.price of zero is preserved (not replaced by the parent price)
    - Per-breakdown values reflect the correct fallback logic
    
    Co-authored-by: jonhall145 <105321987+jonhall145@users.noreply.github.com>

- use wine price as fallback on cellar value page
    
    Same issue as whisky: the cellar value page was only summing
    StorageItem.price, missing bottles priced at the wine level.
    Now uses Coalesce(item.price, wine.price) to match the home page.
    
    Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- use whisky price as fallback on cellar value page
    
    The cellar value page was only summing storage item prices, skipping
    bottles where price is set on the whisky record rather than the item.
    Now uses the same Coalesce(item.price, whisky.price) logic as the
    home page, so both totals match.
    
    Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- show cask-type colours for whisky cells in storage grid

- missing blank line in whisky_tags.py causing flake8 E302 CI failure

- add missing blank line in whisky_tags.py to fix flake8 E302
    
    Co-authored-by: jonhall145 <105321987+jonhall145@users.noreply.github.com>

- align test assertions and secure lint-py shell injection vector

- assert wine_type_class in tests and secure lint-py against shell injection
    
    Co-authored-by: jonhall145 <105321987+jonhall145@users.noreply.github.com>

- separate wine_type display label from CSS class for whisky storage grid
    
    Co-authored-by: jonhall145 <105321987+jonhall145@users.noreply.github.com>

- show cask-type colours for whisky cells in storage grid
    
    Storage grid was showing no colour for whisky bottles because the
    wine_type values ("Single Malt", "Blended", etc.) had no CSS mapping.
    Now uses cask category (bourbon/sherry/other) matching the card view.
    Also fixes Makefile lint-py to use standalone Docker containers so the
    pre-commit hook works without a running web service.
    
    Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- prevent webpack auto-splitting synchronous chunks into unnamed files
    
    global chunks:'all' was causing shared synchronous modules (eg dnd-kit
    utilities) to be split into unnamed numbered chunks (159.js, 354.js,
    385.js, 730.js). these were never loaded by templates, breaking the
    storage grid at runtime when storage_grid.js tried to require them.
    
    change global to chunks:'async' so only named cachegroups (react-vendors,
    leaflet-vendors, fontawesome-vendors) do synchronous chunk splitting.
    everything else bundles into its entry point as before.
    
    Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- extract font awesome into named css chunk for reliable loading
    
    webpack was splitting fa css into an unnamed numbered chunk (595.css)
    in the ghcr build due to a stale gha layer cache, causing icons to
    not load since templates only include base.css.
    
    add an explicit fontawesome-vendors cacheGroup so fa always ends up
    in a predictable named file, and include it in base.html.
    
    Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- build frontend stage natively on x86 in rpi4 docker image
    
    running the node/webpack build under qemu arm64 emulation causes
    parallel terser workers to fail silently, resulting in missing
    bundles (react-vendors.js) and font files in the ghcr image.
    
    webpack output is platform-agnostic so there is no need to cross-
    compile it - only the python runtime stage needs linux/arm64.
    
    Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- run ci on push to main and fix whisky-deploy image build
    
    - add push trigger to ci.yml so migration conflicts are caught after prs merge to main
    - fix whisky-deploy to build via wine-web (which has the build context) so it actually rebuilds the image
    
    Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- merge conflicting whisky 0012 migrations
    
    Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- use --force-recreate --no-deps --no-build in ghcr-deploy
    
    Co-authored-by: jonhall145 <105321987+jonhall145@users.noreply.github.com>

- lower coverage threshold from 80% to 59%
    
    Co-authored-by: jonhall145 <105321987+jonhall145@users.noreply.github.com>

- escape and mark_safe HTML in whisky template tag fallback branches
    
    Co-authored-by: jonhall145 <105321987+jonhall145@users.noreply.github.com>

- make Any option selectable on mobile filters
    
    Replace empty_label with explicit choice for better mobile compatibility.
    
    Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- separate Has Window into its own filter
    
    Ready to Drink filter now only has Yes/No/Any options.
    Has Drink Window is now a separate filter.
    
    Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- enable pointer events on tooltip to allow clicking wine name
    
    The tooltip had `pointer-events: none` which prevented all click and
    tap events from reaching the clickable wine name link. Changed to
    `pointer-events: auto` to make the tooltip interactive.
    
    This was the root cause preventing users from tapping the wine name
    link on mobile (and clicking on desktop).
    
    Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- make tooltips stay visible on mobile for clickable wine names
    
    The tooltip was disappearing immediately when lifting finger on mobile,
    preventing users from tapping the wine name link.
    
    Changes:
    - Removed onTouchEnd handler that was closing tooltip immediately
    - Added document-level touch listener to close tooltip when tapping outside
    - Added preventDefault on touch to prevent immediate cell click
    - Empty cells now properly close tooltip on tap
    
    Mobile behavior now:
    - Tap wine cell → tooltip appears and stays visible
    - Tap wine name in tooltip → navigate to wine detail page
    - Tap another cell → new tooltip appears
    - Tap outside grid → tooltip closes
    
    Desktop behavior (hover) unchanged.
    
    Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- add mobile touch support for clickable wine names in grid
    
    Adds touch event handlers to storage grid cells so the tooltip with
    clickable wine names appears when users tap cells on mobile devices.
    
    Changes:
    - wine_cellar/react/storage_grid.tsx: Add onTouchStart/onTouchEnd handlers
    - Tooltip now shows on tap for mobile users
    - Wine name link is now accessible on mobile
    - docs/storage.md: Update documentation to clarify mobile behavior
    
    Mobile Behavior:
    - Tap any wine cell to show tooltip
    - Tap wine name in tooltip to navigate to wine detail page
    - Tap elsewhere or remove finger to hide tooltip
    
    Desktop behavior (hover) remains unchanged.
    
    Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- Fix wine count being squared due to aggregate JOIN issue
    
    - Separate total_wines count into its own query to avoid JOIN issues
    - Change "Wines in Stock" to "Bottles in Stock" for clarity
    - When multiple Count() aggregations with filters are in single aggregate(),
      JOINs from filtered counts can affect other counts unexpectedly
    - Using simple .count() for total wines avoids this issue
    
    Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- Remove obsolete hardware tests and fix barcode service tests
    
    - Remove hardware test files (hardware app code was cleaned up previously)
    - Fix barcode service mock setup for Unicode decode error tests
    - Add missing database migrations for hardware models
    - Add user language field migration
    
    Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- Prepopulate row/column on bottle edit form to preserve location

- Use simple dropdown for bottle rating instead of star widget

- Add rating to grid tooltip and CSS styling

- Handle non-square thumbnails properly in wine detail view
    
    - Change object-fit from cover to contain to prevent cropping
    - Use max-height instead of fixed height for flexible sizing
    - Add flexbox centering to keep images centered in container
    
    Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>

- Better error handling in vision extraction JS
    
    - Check response.ok before parsing JSON
    - Show actual error status in user message
    - Prevents SyntaxError when server returns HTML error page
    - User now sees 'Server error: 500' instead of generic message

- Add @login_required decorator to vision AJAX endpoint

- Reset file pointer after reading in vision extraction
    
    - Call image_file.seek(0) after reading to prevent 'file changed' error
    - Allows files to be read again when user submits the form
    - Files are now properly preserved across AJAX request and form submission

- Bypass form validation for vision extraction button
    
    - Don't validate required fields when clicking 'Auto-fill from Images'
    - Extract images directly from request.FILES instead of form.cleaned_data
    - Users can now trigger vision extraction without filling required fields first
    - Form is auto-filled from vision results and can be reviewed before submitting

- correct models documentation inaccuracies

- address review comments on models documentation
    
    Co-authored-by: jonhall145 <105321987+jonhall145@users.noreply.github.com>

- **wine details**: order stock items by storage, row, column
- **stock**: make adding a bottle to a previously occupied slot work.
- **deps**: update react monorepo to v19.2.3
- **wine_card**: wrap image in a fixed-size container
- **deps**: update react monorepo to v19.2.1
- **wine detail**: fix image carousel buttons not working    
    - use consistent button icons
    - fix template structure and js element querying

- **wine list**: fix filtering getting lost on page change
- **docker**: fix pip not installing optional dependencies
- **deps**: update dependency @babel/runtime to v7.28.4
- **wine_card**: add missing maring-top and make detail container use available space
- **deps**: update dependency barcode-detector to v3.0.8
- **filters**: don't show wines with only deleted stock items
- **deps**: update dependency barcode-detector to v3.0.7
- **stats**: don't count removed bottles
- **storage**: add more validation and tests for the stock add view
- **storage**: fix broken stock adding
- **map**: change boolean value for the popup close button fixes #467
- **deps**: update react monorepo to v19.2.0
- **deps**: update font awesome to v7.1.0
- **deps**: update dependency barcode-detector to v3.0.6
- **deps**: update font awesome to v7.0.1
- **deps**: update font awesome to v7
- **deps**: update dependency @maplibre/maplibre-gl-leaflet to v0.1.3
- **deps**: update react monorepo to v19.1.1
- **deps**: update dependency @maplibre/maplibre-gl-leaflet to v0.1.2
- **deps**: update dependency @maplibre/maplibre-gl-leaflet to v0.1.1
- **deps**: update dependency barcode-detector to v3.0.5
- **deps**: update dependency barcode-detector to v3.0.4
- **deps**: update dependency barcode-detector to v3.0.2
- **deps**: update dependency react-barcode-scanner to v4
- **deps**: update react monorepo to v19.1.0
- **deps**: update dependency react-barcode-scanner to v3.2.1
- **deps**: update dependency react-barcode-scanner to v3.2.0
- **deps**: update dependency tom-select to v2.4.3
- **deps**: update dependency react-barcode-scanner to v3.1.0
- **deps**: update dependency tom-select to v2.4.2
- **deps**: update font awesome to v6.7.2

### perf

- add database indexes for common queries
    
    Wine model:
    - Index on (user, wine_type) for filtered wine lists
    - Index on name for search queries
    - Index on barcode for barcode lookups
    
    StorageItem model:
    - Index on (user, deleted) for bottle queries
    - Index on (storage, row, column) for position lookups
    
    Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>


### refactor

- deduplicate templates into shared core templates (phase 5)
    
    Move wine and whisky app-specific templates to shared core templates,
    extract homepage includes, and update views to use core template paths.
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- extract remaining duplicated views and filter helpers to core (phase 4)
    
    - extract_vision_ajax: shared AJAX vision extraction function (~130 lines saved)
    - BaseLabelScanView: shared camera capture + file upload handling (~50 lines saved)
    - BaseHomePageView: shared dashboard stats (value, stock, drinks, wishlist) (~140 lines saved)
    - BaseMergeConfirmView: shared duplicate beverage merge logic (~70 lines saved)
    - get_related_model_choices_cached: generic filter choices factory (~60 lines saved)
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- extract shared filters, forms, and create/update views to core (phase 3)
    
    - Create core/filters.py with BeverageFilterMixin and get_country_choices_cached
    - Add BeverageBaseFormMixin and BaseDrinkRecordForm to core/forms.py
    - Add BaseBeverageUpdateView and BaseBeverageCreateView to core/views.py
    - Simplify wine/whisky filters, forms, and views to use shared base classes
    - Net reduction: ~350 lines of duplicated code
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- phase 2 remaining base views and test fixes
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- extract 13 duplicated views and badge helper to core
    
    Move wishlist, drink record, bottle note, reorder reminder, drink
    record create, and cellar value views to base classes in core/views.py.
    Both wine and whisky apps now use thin subclasses with class attributes
    for model/FK differences. Extract _badge_impl helper to core_tags.py
    with consistent escape() usage.
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- extract BottleNoteForm and ReorderReminderForm to core/forms.py
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- extract rating_stars template tag to core/templatetags
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- extract TomSelectMixin to core/forms.py
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- extract base64_to_uploaded_file() to core/utils.py
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- merge wine_carousel and storage_view_toggle into base.js
    
    Both scripts have lazy-init guards and are safe to include on every
    page. Removes two separate webpack entry points and their per-page
    script tags, reducing HTTP requests on detail pages.
    
    Also fixes lint-html Makefile target to strip host paths when
    running djlint inside Docker (matching lint-py behavior).
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- adopt household mixins on wine/whisky views
    
    Add RequireHouseholdMixin to read-only views and RequireMemberMixin
    to mutation views across both wine and whisky apps, replacing the
    ad-hoc authorization pattern with the proven mixin hierarchy from
    the household app. Existing inline get_active_household() calls are
    left as-is for now — they're redundant but harmless.
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- move storage URLs to storage/urls.py
    
    Extract inline storage URL patterns from conf/urls.py into a
    self-contained wine_cellar/apps/storage/urls.py, following Django
    convention. No URL changes — just reorganization.
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

- move `classify_cask_type` out of templatetags into `whisky/utils.py`

- move classify_cask_type to whisky/utils.py
    
    Co-authored-by: jonhall145 <105321987+jonhall145@users.noreply.github.com>

- Apply code formatting and style improvements
    
    - Format long lines to comply with PEP 8 standards
    - Reorder imports alphabetically for consistency
    - Extract repeated mock paths to constants in tests
    - Improve code readability with better line breaks
    - Maintain all functionality while improving maintainability
    
    Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>


