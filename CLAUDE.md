# Claude AI Agent Configuration

This file documents capabilities and tools available when working with Claude on this project.

## UI Testing & Browser Automation

Claude has access to browser automation tools for inspecting and testing UI:

### Installed Tools

- **Playwright** - Cross-browser automation framework
  - Chromium browser installed and configured
  - Can take screenshots, capture console errors, and interact with pages
  - Useful for visual regression testing and accessibility checks

- **Puppeteer** - Headless Chrome automation (globally installed)

### Usage Examples

```javascript
// Basic page inspection with Playwright
const { chromium } = require('playwright');

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.goto('http://localhost:8003/');

// Take screenshot
await page.screenshot({ path: 'screenshot.png', fullPage: true });

// Capture console errors
page.on('console', msg => {
  if (msg.type() === 'error') console.log('Error:', msg.text());
});

// Check for accessibility issues
const imagesWithoutAlt = await page.$$eval('img:not([alt])', imgs => imgs.length);

await browser.close();
```

### Common UI Checks

When inspecting pages, Claude can check for:

1. **Console errors** - JavaScript errors, failed resource loads
2. **Missing alt text** - Images without accessibility attributes
3. **Empty links** - Links without text or href
4. **Form accessibility** - Inputs without associated labels
5. **Horizontal overflow** - Layout issues causing scrollbars
6. **Missing page titles** - SEO and accessibility concern
7. **HTTP errors** - 4xx/5xx status codes

### Running the Dev Server

```bash
# HTTP (standard development)
./run_local.sh

# HTTPS (required for camera access on non-localhost)
./run_https.sh
```

### HTTPS for Camera Access

Mobile browsers require HTTPS to access the camera. Use `./run_https.sh` which:
- Uses self-signed SSL certificates (auto-generated in `ssl/`)
- Runs on https://0.0.0.0:8000
- Requires accepting the certificate warning in browser

### Test User

A test user exists for UI testing:
- **Username:** testuser
- **Password:** testpass123

## Project Context

### Technology Stack

**Backend:**
- Django 5.2.9 with Python 3.11+
- PostgreSQL 16 (production) / SQLite (development)
- Celery 5.6.0 with django-celery-beat for background tasks

**Frontend:**
- React 19.2.3 with TypeScript
- Leaflet for map visualization
- Barcode scanner components
- Webpack 5 build system

**Key Dependencies:**
- django-allauth for authentication
- pytest for testing
- Whitenoise for static file serving
- Gunicorn for production serving

### Project Structure

```
wine_cellar/
├── apps/
│   ├── wine/       # Wine tracking and management
│   ├── storage/    # Inventory and storage locations
│   └── user/       # User management and settings
├── templates/      # Django templates
├── react/          # React components (barcode scanner, maps)
├── assets/         # CSS, JS source files
└── conf/           # Django settings

tests/              # Pytest test suite
docs/               # MkDocs documentation
fixtures/           # Sample data (grapes, wines, stock)
```

### Database Models

**Wine:** Core wine information (name, vintage, country, type, rating, ABV, images)
**StorageItem:** Inventory tracking with pricing and location
**Shelf:** Physical storage locations
**UserSettings:** Per-user preferences (currency, date format)

For detailed documentation, see:
- [Architecture](docs/architecture.md)
- [Models](docs/models.md)
- [API Reference](docs/api.md)

## Development Commands

```bash
make install    # Install dependencies
make server     # Start dev server (port 8003)
make watch      # Dev server with frontend rebuild
make pytest     # Run backend tests
make lint       # Run all linters
make fixtures   # Load sample data
```

## Key Directories

- `wine_cellar/` - Main Django application
- `wine_cellar/templates/` - Django templates
- `wine_cellar/apps/` - Django apps (wine, storage, user)
- `wine_cellar/react/` - React components
- `tests/` - Test suite
- `static/` - Static assets

## Notes for Claude

1. **Always start the dev server** before running UI tests
2. **Use port 8765** (or another unused port) for testing to avoid conflicts
3. **Clean up test artifacts** (screenshots, test scripts) after inspection
4. **The jsi18n endpoint requires authentication** - script tag is conditionally loaded
5. **Map tiles require internet access** - expect fetch errors in isolated environments
6. **Only update jonhall145 repos** - Do not create PRs to upstream repos (the-broke-sommeliers). Only push to origin (jonhall145)
7. **Avoid full rebuilds for tests** - Tests should not require a full frontend rebuild as this is slow and causes timeout issues. Use `make pytest` directly for backend tests.

## Lessons Learned

These patterns are derived from previous development sessions to improve accuracy and efficiency.

### Mobile-First Development

The user is a **mobile-first user**. Always:
- Test UI changes on mobile viewports
- Verify touch interactions work (not just click events)
- Check that dropdowns/selects are usable on mobile (especially TomSelect)
- Remember HTTPS is required for camera/barcode scanning on mobile

### Common Pitfalls

**TomSelect Dropdowns:**
- "Any/All" options must have `allowEmptyOption: true` in TomSelect config
- Mobile Safari has issues with empty-value options - test thoroughly
- Filter dropdowns should always include an "Any" choice as the default

**Aggregate Queries:**
- Be careful with JOINs in Django querysets that include `.annotate()` - they can cause count/sum values to be multiplied (e.g., "wine count squared" bug)
- Use `.distinct()` or subqueries when combining filters with aggregates
- Verify bottle counts vs wine counts when filtering

**Static Files & CSS:**
- Changes to CSS/JS require `make watch` or `npm run build` to be visible
- Production requires `collectstatic` - use `./run_prod_https.sh` which handles this
- Check browser cache / use incognito when CSS changes aren't visible

### Deployment Checklist

For production deployment to meshnet:
1. Run `make lint` - fix any issues before deploying
2. Run `make pytest` - ensure tests pass
3. Static files are collected automatically by prod scripts
4. HTTPS is required for camera access - use `./run_prod_https.sh`

### Common Fix Patterns

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| Filter "Any" not selectable on mobile | TomSelect config | Add `allowEmptyOption: true` |
| Wrong count when filtering | JOIN with aggregate | Use `.distinct()` or subquery |
| CSS changes not visible | Browser cache | Hard refresh / incognito |
| Camera not working | Not HTTPS | Use HTTPS server script |
| 500 error on forms | Missing form field | Check model changes vs form fields |

### Workflow Preferences

- **Commit style**: Short, lowercase messages describing the change
- **Stage-commit-push**: User often requests these as a single action
- **Lint before commit**: Always run `make lint` and fix issues before committing
