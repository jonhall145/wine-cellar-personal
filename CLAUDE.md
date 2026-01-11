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

See `agents.md` for comprehensive project documentation including:
- Technology stack (Django, React, PostgreSQL)
- Project structure
- Development workflows
- Database schema
- Testing approach

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
