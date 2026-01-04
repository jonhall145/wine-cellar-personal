# CSS Debugging & Icon Centering

## Overview

Techniques for debugging CSS issues and fixing common centering problems, especially with icon fonts like FontAwesome.

## Debugging with Playwright

### Inspect Computed Styles

```javascript
const styles = await page.evaluate(() => {
  const elements = document.querySelectorAll('.target-class');
  return Array.from(elements).map(el => {
    const computed = window.getComputedStyle(el);
    return {
      className: el.className,
      background: computed.background,
      backgroundColor: computed.backgroundColor,
      borderRadius: computed.borderRadius,
      display: computed.display,
      width: computed.width,
      height: computed.height,
      alignItems: computed.alignItems,
      justifyContent: computed.justifyContent
    };
  });
});
console.log(JSON.stringify(styles, null, 2));
```

## Icon Centering Patterns

### Problem: Icons Off-Center in Circles

FontAwesome icons with built-in circles (e.g., `fa-check-circle`) may have the inner element slightly off-center due to font glyph design.

### Solution 1: Use CSS-Based Circles

Instead of relying on icon glyphs with circles, create your own circular background:

```css
.icon-container i {
  font-size: var(--font-xl);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.5em;
  height: 2.5em;
  background: var(--bg-secondary);
  border-radius: 50%;
  line-height: 1;
}
```

Then use simpler icons without built-in circles:
- `fa-check` instead of `fa-check-circle`
- `fa-heart` (solid/regular) instead of icons with backgrounds

### Solution 2: Flexbox Parent Container

Ensure the parent container uses flexbox for centering:

```css
.container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
```

### Solution 3: Proper HTML Structure

Separate icon and text into distinct elements:

```html
<!-- Before: Icon and text inline -->
<p class="empty-state"><i class="fa-solid fa-check"></i> No items</p>

<!-- After: Separate elements for flex layout -->
<div class="empty-state">
  <i class="fa-solid fa-check"></i>
  <span>No items</span>
</div>
```

## Common Centering Issues

### Issue: `display: block` Doesn't Center Content

`display: block` with `margin: 0 auto` centers the element but not its contents.

**Fix:** Use flexbox:

```css
.element {
  display: flex;
  align-items: center;
  justify-content: center;
}
```

### Issue: Icon Size Inconsistency

FontAwesome icons have varying widths. Use fixed dimensions:

```css
.icon {
  width: 1em;
  height: 1em;
  text-align: center;
}
```

### Issue: Line Height Affecting Vertical Center

Reset line-height for icons:

```css
.icon {
  line-height: 1;
}
```

## Webpack/Build Considerations

When CSS is bundled (e.g., via Webpack), changes to source files require rebuilding:

```bash
npm run build
```

For development, source files are in `wine_cellar/assets/css/` and compiled to `wine_cellar/static/`.

**Quick Fix:** Edit both source and compiled CSS for immediate effect, then rebuild later.

## CSS Variables Used

```css
:root {
  --font-xl: 1.5rem;
  --bg-secondary: #f5f5f5;
  --spacing-sm: 0.5rem;
}
```

## Verification

After CSS changes, take a screenshot to verify:

```javascript
await page.screenshot({ path: 'after-fix.png', fullPage: true });
```

Compare before/after screenshots to confirm the fix.
