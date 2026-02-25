# Playwright UI Testing Examples

## Basic Page Inspection

```javascript
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

For more examples, see the test suite in `tests/` and use Playwright's official documentation.
