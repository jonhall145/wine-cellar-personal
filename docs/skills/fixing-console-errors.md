# Fixing JavaScript Console Errors

## Overview

Techniques for identifying and fixing JavaScript console errors detected during UI testing.

## Common Console Errors

### MIME Type Errors

**Error:**
```
Refused to execute script from 'http://localhost/path' because its MIME type ('text/html') is not executable
```

**Cause:** JavaScript file URL is returning HTML (often a login redirect).

**Fix:** Make the endpoint public or conditionally load the script:

```django
{# Before: Always loads, fails for unauthenticated users #}
<script src="{% url 'javascript-catalog' %}"></script>

{# After: Only loads for authenticated users #}
{% if user.is_authenticated %}
    <script src="{% url 'javascript-catalog' %}"></script>
{% endif %}
```

### Failed Fetch Errors

**Error:**
```
AJAXError: Failed to fetch (0): https://external-api.com/resource
```

**Cause:** Network request failed (CORS, offline, blocked).

**Solutions:**
1. Add CORS headers if you control the API
2. Use a proxy for external resources
3. Add error handling in JavaScript:

```javascript
try {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return await response.json();
} catch (error) {
  console.warn('Resource unavailable:', url);
  return null; // Graceful fallback
}
```

### Module Not Found

**Error:**
```
Error: Cannot find module 'package-name'
```

**Fix:** Install the package locally:

```bash
npm install package-name --save-dev
```

## Detecting Errors with Playwright

```javascript
const consoleErrors = [];
const pageErrors = [];

page.on('console', msg => {
  if (msg.type() === 'error') {
    consoleErrors.push({
      page: currentPage,
      message: msg.text()
    });
  }
});

page.on('pageerror', error => {
  pageErrors.push({
    page: currentPage,
    error: error.message
  });
});

// Navigate and collect errors
await page.goto(url);
await page.waitForLoadState('networkidle');

// Report errors
if (consoleErrors.length > 0) {
  console.log('Console Errors:', consoleErrors);
}
```

## Categorizing Errors

### Critical (Must Fix)
- MIME type errors blocking scripts
- Uncaught exceptions
- Failed API calls that break functionality

### Warnings (Should Fix)
- Deprecation warnings
- Failed optional resource loads
- Performance warnings

### Informational (Can Ignore)
- Third-party tracking failures
- External tile/map service failures in isolated environments
- Browser extension conflicts

## Django-Specific Fixes

### Static File Issues

Check that static files are being served:

```python
# settings.py
DEBUG = True  # For development
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
```

### JavaScript Internationalization

The `jsi18n` endpoint requires special handling:

```python
# urls.py - Make public if needed by unauthenticated pages
from django.views.i18n import JavaScriptCatalog

urlpatterns = [
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
]
```

Or conditionally include in templates (as shown above).

## Testing After Fixes

Re-run the UI inspection to verify errors are resolved:

```bash
node ui_inspect.js
```

Check the results:
```json
{
  "consoleErrors": [],
  "pageErrors": [],
  "issues": []
}
```
