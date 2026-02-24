# Claude AI Agent Configuration

This file documents capabilities and tools available when working with Claude on this project.

## Project Overview

Primary stack: Python/Django backend, Docker for deployment, Raspberry Pi build server, Cloudflare Tunnel for SSL/routing, R2 for backups. Frontend uses HTML templates with CSS/JS.

## UI Testing & Browser Automation

Claude has access to browser automation tools for inspecting and testing UI:

### Installed Tools

- **Playwright** - Cross-browser automation framework
  - Chromium browser installed and configured
  - Can take screenshots, capture console errors, and interact with pages
  - Useful for visual regression testing and accessibility checks

- **Puppeteer** - Headless Chrome automation (globally installed)

### CLI Testing Tools

- **httpie** (`http`) - Human-friendly HTTP client for API testing
- **jq** - JSON processor for parsing API responses
- **litecli** - SQLite client with autocomplete
- **pgcli** - PostgreSQL client with autocomplete
- **toolong** (`tl`) - Terminal log viewer with live tail
- **htop** - Interactive process viewer
- **ncdu** - Disk usage analyzer
- **imagemagick** (`convert`) - Image processing

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
- Django 5.2.9 with Python 3.12+
- PostgreSQL 16 (production) / SQLite (development)
- Cron-based background tasks (drink-by reminders via management command)

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

## Custom Skills (Slash Commands)

These skills are available for common tasks:

| Skill | Description |
|-------|-------------|
| `/server [cmd]` | Manage production server (start/stop/restart/status/deploy) |
| `/test [cmd]` | Run tests (all/unit/ui/api/db/lint/quick) |
| `/ui-check [page]` | Browser automation UI testing |
| `/api-test [endpoint]` | API endpoint testing with httpie |
| `/db-check [cmd]` | Database integrity and health checks |

### Examples:
```
/server restart     # Restart production server
/test all           # Run all tests in parallel
/ui-check mobile    # Test mobile viewport rendering
/api-test auth      # Test authentication flow
/db-check stats     # Show database statistics
```

## Development Commands

```bash
make install    # Install dependencies
make server     # Start dev server (port 8003)
make watch      # Dev server with frontend rebuild
make pytest     # Run backend tests
make lint       # Run all linters
make fixtures   # Load sample data
```

## Production Deployment Commands

Always use `make` targets rather than calling scripts directly.

```bash
make wine-deploy        # Build Docker image and deploy wine app
make whisky-deploy      # Deploy whisky app (uses same image)

make wine-prod-start    # Start wine container
make wine-prod-stop     # Stop wine container
make wine-prod-restart  # Restart wine container
make wine-prod-status   # Show wine container status
make wine-prod-logs     # Tail wine container logs

make whisky-prod-start    # Start whisky container
make whisky-prod-stop     # Stop whisky container
make whisky-prod-restart  # Restart whisky container
make whisky-prod-status   # Show whisky container status
make whisky-prod-logs     # Tail whisky container logs
```

**Notes:**
- Both apps share the same `wine-cellar:prod` Docker image — `make wine-deploy` builds it for both
- To deploy both apps: run `make wine-deploy` then `make whisky-deploy`
- Do NOT use `deploy-to-prod.sh` — that is the legacy non-Docker path and is no longer used
- Static files and frontend assets are built inside the Docker image automatically
- **Deploy agent should ONLY run `make wine-deploy` then `make whisky-deploy`. Do NOT run lint, tests, or any other steps.**

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
8. **Never change user passwords permanently** - If you need to reset a password for testing, always revert it back to the original before finishing. Do not leave changed passwords.

## Lessons Learned

These patterns are derived from previous development sessions to improve accuracy and efficiency.

### Mobile-First Development

This is a **mobile-first app**. Mobile testing is mandatory, not optional.

**For ALL UI/CSS changes:**
1. Always test on mobile viewport FIRST (390x844 or similar)
2. Use Playwright to take screenshots and measure element sizes
3. Verify buttons/controls are the same size when they should be (use `boundingBox()`)
4. Check vertical alignment of side-by-side elements
5. Ensure touch targets are adequate (minimum 44px)

**Common mobile issues to check:**
- Buttons using `<a>` vs `<button>` tags render differently - normalize with `display: inline-flex`
- Flex containers need `align-items: center` for consistent vertical alignment
- Touch interactions work (not just click events)
- Dropdowns/selects are usable on mobile (especially TomSelect)
- HTTPS is required for camera/barcode scanning on mobile

### Common Pitfalls

**TomSelect Dropdowns:**
- "Any/All" options must have `allowEmptyOption: true` in TomSelect config
- Mobile Safari has issues with empty-value options - test thoroughly
- Filter dropdowns should always include an "Any" choice as the default
- When using `items` to pre-select values, also set `clear=False` or they get wiped

**Aggregate Queries:**
- Be careful with JOINs in Django querysets that include `.annotate()` - they can cause count/sum values to be multiplied (e.g., "wine count squared" bug)
- Use `.distinct()` or subqueries when combining filters with aggregates
- Verify bottle counts vs wine counts when filtering

**Static Files & CSS:**
- Changes to CSS/JS require `make watch` or `npm run build` to be visible
- Production requires `collectstatic` - handled automatically inside the Docker image build
- Check browser cache / use incognito when CSS changes aren't visible

### Deployment Checklist

For production deployment:
1. Run `make lint` - fix any issues before deploying
2. Run `make pytest` - ensure tests pass
3. Run `make wine-deploy` then `make whisky-deploy`
4. Static files and frontend assets are built inside the Docker image automatically

### Common Fix Patterns

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| Filter "Any" not selectable on mobile | TomSelect config | Add `allowEmptyOption: true` |
| Pre-filled field value cleared | TomSelect `clear()` | Add `clear=False` to config |
| Wrong count when filtering | JOIN with aggregate | Use `.distinct()` or subquery |
| CSS changes not visible | Browser cache | Hard refresh / incognito |
| Camera not working | Not HTTPS | Use HTTPS server script |
| 500 error on forms | Missing form field | Check model changes vs form fields |
| Buttons different sizes | `<a>` vs `<button>` display | Add `display: inline-flex` to button class |
| Buttons not vertically aligned | Flex container missing alignment | Add `align-items: center` to parent |

### Workflow Preferences

- **Commit style**: Short, lowercase messages describing the change
- **Stage-commit-push**: User often requests these as a single action
- **Lint before commit**: Always run `make lint` and fix issues before committing
- **Save conversations**: Always save a copy of the conversation to `.claude/logs/` for later review

## Git Workflow

When asked to commit/push, always run pre-commit hooks (lint, type checks) first and fix any failures before attempting the commit.

## Code Conventions

When making changes to shared templates or components used by both wine and whisky apps, always check for hardcoded app-specific references (e.g., wine-specific URLs, service names) and make them generic.

## Testing

After making model/field changes, search ALL test files for references to the old field/model name and update them in a single pass. Do not rely on a single test run to catch everything.

### Conversation Logging

At the end of each session or when significant work is completed, save a summary to:
```
.claude/logs/YYYY-MM-DD_summary.md
```

Include:
- Date and brief description of work done
- Key changes made (files modified, features added, bugs fixed)
- Any issues encountered and how they were resolved
- Pending tasks or follow-ups
