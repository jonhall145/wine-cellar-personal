# UI Testing with Playwright

## Overview

Automated UI testing using Playwright to inspect web pages, capture screenshots, detect console errors, and identify accessibility issues.

## Prerequisites

```bash
# Install Playwright (local to project)
npm install playwright --save-dev

# Install browser and dependencies
npx playwright install chromium
npx playwright install-deps chromium
```

## Basic Usage

### Take Screenshots

```javascript
const { chromium } = require('playwright');

async function captureScreenshot(url, outputPath) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.screenshot({ path: outputPath, fullPage: true });
  
  await browser.close();
}
```

### Capture Console Errors

```javascript
const consoleErrors = [];

page.on('console', msg => {
  if (msg.type() === 'error') {
    consoleErrors.push({ message: msg.text() });
  }
});

page.on('pageerror', error => {
  consoleErrors.push({ error: error.message });
});
```

### Login to Authenticated Pages

```javascript
// For Django with django-allauth
await page.goto('http://localhost:8000/accounts/login/');
await page.fill('input[name="login"]', 'username');
await page.fill('input[name="password"]', 'password');
await page.click('button[type="submit"]');
await page.waitForLoadState('networkidle');
```

## Accessibility Checks

```javascript
async function checkAccessibility(page) {
  const issues = [];
  
  // Images without alt text
  const imagesWithoutAlt = await page.$$eval('img:not([alt])', imgs => imgs.length);
  if (imagesWithoutAlt > 0) {
    issues.push(`${imagesWithoutAlt} images without alt text`);
  }
  
  // Empty links
  const emptyLinks = await page.$$eval('a:not([href]), a[href=""], a[href="#"]', links => 
    links.filter(l => !l.textContent.trim()).length
  );
  if (emptyLinks > 0) {
    issues.push(`${emptyLinks} empty or broken links`);
  }
  
  // Form inputs without labels
  const inputsWithoutLabels = await page.$$eval(
    'input:not([type="hidden"]):not([type="submit"]):not([aria-label])', 
    inputs => inputs.filter(input => {
      const id = input.id;
      if (!id) return true;
      return !document.querySelector(`label[for="${id}"]`);
    }).length
  );
  if (inputsWithoutLabels > 0) {
    issues.push(`${inputsWithoutLabels} form inputs without labels`);
  }
  
  // Horizontal overflow
  const hasOverflow = await page.evaluate(() => 
    document.documentElement.scrollWidth > document.documentElement.clientWidth
  );
  if (hasOverflow) {
    issues.push('Page has horizontal overflow');
  }
  
  return issues;
}
```

## Inspect Computed Styles

```javascript
const styles = await page.evaluate(() => {
  const element = document.querySelector('.my-element');
  const computed = window.getComputedStyle(element);
  return {
    background: computed.backgroundColor,
    display: computed.display,
    width: computed.width,
    height: computed.height
  };
});
```

## Full Page Inspection Script

See `ui_inspect.js` pattern for comprehensive page inspection including:
- Multiple page navigation
- Authentication handling
- Screenshot capture
- Console error logging
- Accessibility checks
- Results output to JSON

## Tips

1. **Use `networkidle`** - Wait for network to be idle before taking screenshots
2. **Set viewport size** - Consistent viewport ensures reproducible screenshots
3. **Handle authentication** - Login once, reuse the browser context for multiple pages
4. **Clean up** - Always close browser and remove temporary files
5. **Port conflicts** - Use non-standard ports (e.g., 8765) to avoid conflicts

## Common Issues

| Issue | Solution |
|-------|----------|
| Missing libraries | Run `npx playwright install-deps chromium` |
| Timeout on maps | Map tiles require internet; expect failures in isolated environments |
| MIME type errors | Check if scripts require authentication |
