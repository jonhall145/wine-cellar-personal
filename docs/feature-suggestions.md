# Feature Suggestions & Improvements

A prioritised list of new features and improvements for the wine cellar application, organised by category. Each suggestion includes estimated complexity and expected user impact.

---

## New Features

### 1. CSV/Excel Import & Export

**Impact: High | Complexity: Medium**

Currently there's no way to bulk-import wines or export the cellar. This is one of the most requested features in any collection app.

- **Import**: Upload a CSV/Excel file to create wines and stock entries in bulk. Include a column-mapping step so users can match their spreadsheet columns to model fields.
- **Export**: Download the full cellar as CSV/Excel/PDF. Essential for insurance documentation, sharing with sommeliers, or migrating data.
- **Suggested scope**: Start with CSV import/export for wines + stock, expand to drinks history and wishlist.

---

### 2. Recently Viewed Wines

**Impact: High | Complexity: Low**

Track the last 5-10 wines a user has viewed and display them prominently on the homepage. This is a small change with outsized usability benefit - users frequently revisit the same wines when deciding what to drink, adding stock, or updating notes.

- Store recent views in the user's session (no model changes needed)
- Display as a horizontal card row on the homepage above or alongside existing sections
- Show wine name, thumbnail, vintage, and bottle count
- Clicking goes straight to the wine detail page
- Clear/dismiss individual items or the whole list

---

### 3. Smart Collections / Custom Tags

**Impact: High | Complexity: Medium**

Users currently have no way to organise wines beyond the built-in filters (type, country, vintage). Custom collections would allow grouping like "dinner party picks", "investment wines", "summer drinking", etc.

- New `Collection` model with name, description, colour/icon
- M2M relationship to Wine
- Filter wine list by collection
- Quick-add from wine detail page
- Drag wines between collections

---

### 4. Full REST API

**Impact: High | Complexity: High**

The app currently only has a few AJAX endpoints. A proper REST API (using Django REST Framework) would enable:

- Future mobile app development (native iOS/Android)
- Third-party integrations (wine databases, price trackers)
- Zapier/IFTTT automation
- Public API for household members using different clients
- Start with read-only endpoints, then add write operations

---

### 5. Progressive Web App (PWA) Support

**Impact: High | Complexity: Medium**

As a mobile-first app, PWA support would significantly improve the experience:

- **Add to homescreen** with app icon and splash screen
- **Offline access** to view cellar contents without connectivity
- **Background sync** for changes made offline
- **Push notifications** for drinking window alerts and reorder reminders (replacing email-only)
- Service worker for caching static assets and recent data

---

### 6. Wine Journey Timeline

**Impact: Medium | Complexity: Medium**

A visual timeline showing the user's wine journey over time:

- When wines were added to the cellar
- When bottles were consumed (with ratings)
- Price trends of purchases
- Milestones ("100th bottle added", "first 3-star wine")
- Monthly/yearly consumption patterns as a scrollable timeline
- Could use a simple vertical timeline UI component

---

### 7. Advanced Analytics Dashboard

**Impact: Medium | Complexity: Medium**

The current stats page is basic. A richer analytics dashboard could include:

- **Spending trends**: Monthly/yearly spend with charts
- **Consumption heatmap**: Calendar view showing when wines are consumed
- **Country/region breakdown**: Donut charts of cellar composition
- **Rating distribution**: Histogram of ratings across wines and drinks
- **Grape variety analysis**: Most collected and highest-rated varietals
- **Cellar age profile**: Distribution of vintages, average age
- **Value per bottle over time**: Track whether the cellar is appreciating
- Could use Chart.js or a lightweight charting library

---

### 8. Price Tracking Completion

**Impact: Medium | Complexity: Medium-High**

The `PriceHistory`, `Source`, and `price_selector` fields exist but the scraping functionality isn't implemented. Completing this would add:

- Scheduled price checks using configured CSS selectors
- Price trend charts on wine detail pages
- Alerts when prices drop below a threshold
- Integration with the wishlist (notify when wishlist wine is affordable)
- Average market value vs. purchase price comparison

---

## Improvements to Existing Features

### 9. Storage Grid Enhancements

**Impact: Medium | Complexity: Medium**

The React storage grid is already functional. Improvements:

- **Colour coding options**: Toggle between colouring by wine type, rating, age, or value
- **Utilisation percentage**: Show how full each storage is
- **Multi-bottle cells**: Support for bins/slots that hold multiple bottles (common in large cellars)
- **Storage overview**: Bird's eye view of all storages with mini-grids
- **Print view**: Printable storage layout for sticking on the cellar door

---

### 10. Wishlist Improvements

**Impact: Medium | Complexity: Low-Medium**

- **Link to price tracking**: Auto-notify when a wishlisted wine drops below the price limit
- **Share wishlist**: Generate a shareable link (useful for gift-giving occasions)
- **Convert to wine**: One-click to create a Wine entry from a wishlist item when purchased
- **External links**: Add a URL field to link to where the wine can be purchased

---

### 11. Notification Centre

**Impact: Medium | Complexity: Medium**

Currently notifications are email-only via cron. Add an in-app notification system:

- Bell icon in the header with unread count badge
- Notification types: drinking window approaching, low stock, price alerts, household invitations
- Mark as read/dismiss
- Notification preferences per type (email, in-app, both, none)
- Replaces the separate alerts and reorder reminder pages with a unified view

---

### 12. Drink History Enhancements

**Impact: Medium | Complexity: Low-Medium**

- **Photo capture**: Attach a photo when logging a drink (the bottle, the meal, the setting)
- **Structured tasting wheel**: Interactive flavour wheel for selecting taste descriptors instead of free-text
- **Vintage comparison**: Side-by-side comparison of ratings/notes for different vintages of the same wine
- **Social sharing**: Share a drink log entry as an image card (for Instagram, etc.)
- **Quick log**: One-tap "just drank this" from the bottle detail page without filling in all fields

---

### 13. Vision Extraction Refinements

**Impact: Medium | Complexity: Low**

The Claude vision integration works well. Refinements:

- **Per-field confidence indicators**: Show green/yellow/red next to each extracted field so users know what to double-check
- **Learning from corrections**: Track which fields get corrected most often to improve prompts over time
- **Batch scanning**: Scan multiple bottles in succession without returning to the list
- **Better appellation matching**: Use fuzzy matching against the appellation database to improve hit rate
- **Extraction history on wine detail**: Show "this wine was originally extracted from label scan" with a link to the extraction log

---

## Technical / Infrastructure Improvements

### 14. Background Task Queue

**Impact: Medium | Complexity: Medium**

Replace cron-based tasks with a proper task queue (Django-Q2, Celery, or Huey):

- Drink-by reminders as scheduled tasks instead of cron
- Price scraping as periodic tasks
- Thumbnail regeneration as async tasks
- Email sending as background jobs
- Better monitoring and retry logic
- Lighter weight option: `django-q2` with the ORM broker (no Redis needed)

---

### 15. Database Query Optimisation

**Impact: Medium | Complexity: Low-Medium**

- Add `select_related` / `prefetch_related` calls to views that access related models (wine images, storage items, grapes)
- Add database indexes on frequently filtered fields not yet indexed
- Review the aggregate queries flagged in CLAUDE.md (JOIN + annotate multiplication bugs)
- Add query count assertions in tests to prevent N+1 regressions
- Consider `django-auto-prefetch` for automatic optimisation

---

### 16. Improved Test Coverage

**Impact: Medium | Complexity: Medium**

- **Integration tests**: Test full user flows (scan label -> create wine -> add to stock -> consume -> rate)
- **Household permission tests**: Verify role-based access (viewer can't edit, member can't delete household, etc.)
- **API endpoint tests**: Test all AJAX endpoints with various authentication states
- **Mobile UI tests**: Playwright tests for mobile viewports on critical flows
- **Performance tests**: Load test the most common views with realistic data volumes

---

### 17. Accessibility Improvements

**Impact: Medium | Complexity: Low-Medium**

- **ARIA labels** on interactive elements (storage grid cells, filter dropdowns, scanner buttons)
- **Keyboard navigation** for the storage grid (currently requires mouse/touch)
- **Screen reader support** for stats and charts
- **Colour contrast audit** across all themes
- **Skip navigation links** for keyboard users
- Automated accessibility testing with axe-core in the Playwright test suite

---

## Quick Wins (Low Effort, Nice to Have)

| Suggestion | Effort | Description |
|---|---|---|
| Dark mode | Low | CSS custom properties + media query for `prefers-color-scheme` |
| Duplicate detection | Low | Warn when adding a wine that closely matches an existing entry |
| Bottle count on nav | Low | Show total bottle count in the header/nav bar |
| Sorting on all list views | Low | Add sortable column headers to wine list, bottle list, drink history |
| "Random bottle" picker | Low | "What should I drink tonight?" button that picks a random in-stock wine |
| QR code generation | Low | Generate a QR code for any wine that links to its detail page - print and stick on shelves so anyone can scan a bottle's spot to see full details |
| Keyboard shortcuts | Low | `n` for new wine, `s` for scan, `/` for search |
| Empty state illustrations | Low | Friendly empty states for new users with no wines/bottles/drinks |
| Cellar summary email | Low | Weekly/monthly digest email with cellar stats and upcoming drinking windows |

---

## Review Notes

Observations and suggestions from reviewing this feature list (March 2026).

### Prioritisation Recommendation

**#2 Recently Viewed Wines** is the highest-ROI item on the list — low complexity, high impact, no model changes required. Recommend tackling this first.

### Complexity Corrections

- **#5 PWA Support**: Background sync and offline-first architecture are notoriously tricky in practice. Real-world complexity is closer to **High** than Medium, especially for data sync conflict resolution.
- **Dark mode (Quick Wins)**: Marked as Low effort, which is accurate only if CSS custom properties are already used throughout. If styles use hardcoded colour values, the migration effort increases significantly.

### Strategic Observations

- **#4 Full REST API**: Marked High impact / High complexity. Worth questioning whether this is needed now — unless there's a concrete mobile app plan, this is speculative and could be deferred indefinitely. The existing AJAX endpoints may be sufficient.
- **#8 Price Tracking**: The CSS selector scraping approach is inherently fragile — retailer sites change layouts frequently, breaking selectors. For a personal app, consider API-based price lookups or simple manual price logging instead of maintaining scrapers.
- **#14 Background Task Queue**: django-q2 with the ORM broker is the right fit for a Raspberry Pi deployment. Celery + Redis would be overkill for this scale.

### Progress (improvements/comprehensive-sprint branch)

Work completed or started as of March 2026:

| Item | Status | What was done |
|---|---|---|
| #1 CSV/Excel Import & Export | **Partial** | CSV/JSON export added (`wine_cellar/apps/wine/export.py`). Import not yet implemented. |
| #7 Advanced Analytics Dashboard | **Partial** | Chart.js charts added to consumption stats page. |
| #11 Notification Centre | **Partial** | Per-user drink reminder preferences added (new `UserSettings` fields, updated `send_drink_reminders` command). No in-app notification bell yet. |
| #15 Database Query Optimisation | **Partial** | N+1 fix for Wine image properties. Homepage stats caching with signal-based invalidation. |
| #16 Improved Test Coverage | **Partial** | E2E scaffolding with Playwright (auth, CRUD, list tests). Image processing and settings integration tests added. |

**Also completed (not on this list):**
- Sentry SDK integration (gated by `SENTRY_DSN`)
- JSON structured logging for production
- Audit logging helpers integrated into base CRUD views
- Split `views.py` (1049 lines) into a `views/` package (11 modules)
- Bulk operations view (delete, update drink-by year)
- Wildcard import cleanup in settings modules
- CONTRIBUTING.md updated with accurate project info

### Missing Items to Consider

| Suggestion | Effort | Description |
|---|---|---|
| Full-text search | Medium | Search across tasting notes, wine notes, and descriptions — not just name/vintage filters |
| Multi-language / i18n | Medium | Django has built-in i18n support; useful if the app is shared with non-English-speaking household members |
| User-facing backup & restore | Low-Medium | Let users export/import their complete account data (wines, notes, history) independently of infrastructure-level R2 backups |
