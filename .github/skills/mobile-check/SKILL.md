---
name: mobile-check
description: Run a mobile-first UI check with the right local server, viewport, and repo-specific pitfalls in mind.
---

Use this skill when the user invokes `/mobile-check` for a page, route, or UI change.

When this skill is active:
1. Prefer delegating to the `mobile-ui-checker` custom agent.
2. Start the right server for the requested flow; prefer HTTPS when camera or barcode scanning is involved.
3. Check the affected page on a mobile viewport first, around `390x844`, unless the user requests a different size.
4. Look for console errors, horizontal overflow, broken alignment, inconsistent button sizing, missing labels, and poor touch-target sizing.
5. Pay special attention to repo-specific mobile pitfalls like TomSelect behavior and mixed link/button styling.
6. Clean up temporary artifacts created during the check.
