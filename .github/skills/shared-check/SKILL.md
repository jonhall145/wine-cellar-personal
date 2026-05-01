---
name: shared-check
description: Validate shared wine/whisky surfaces after changes to common templates, views, forms, or UI code.
---

Use this skill when the user invokes `/shared-check` or when a change may affect both wine and whisky experiences.

When this skill is active:
1. Prefer delegating to the `shared-surface-checker` custom agent.
2. Inspect shared templates, forms, views, URLs, and front-end code for wine-specific assumptions.
3. Validate both wine and whisky modes when the touched code is shared.
4. Use standard repository checks for wine behavior and whisky-scoped commands when whisky behavior is in play.
5. Call out any gap where only one mode could be exercised.
6. Keep fixes generic and avoid introducing new app-specific hardcoding into shared code.
