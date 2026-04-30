---
name: lint
description: Run the repository lint flow, fix safe issues, and leave a focused summary.
---

Use this skill when the user invokes `/lint`, optionally followed by a scope such as `all`, `py`, `js`, `html`, or one or more file paths.

When this skill is active:
1. Interpret the remainder of the user's command as the requested lint scope.
2. Prefer delegating to the `lint-fixer` custom agent.
3. Default to `make lint` when no narrower scope is provided.
4. Use repository-native helpers for scoped work when appropriate:
   - `make lint-py <paths>`
   - `make lint-html <paths>`
   - `make lint-js-fix`
5. Fix only issues that are in scope or directly coupled to them.
6. Do not create commits, tags, pushes, or deploys unless the user explicitly asks.
