---
name: bump-version
description: Bump the project version safely using the repository's existing versioning commands.
---

Use this skill when the user invokes `/bump-version` with `patch`, `minor`, or `major`.

When this skill is active:
1. Prefer delegating to the `version-bumper` custom agent.
2. If the bump type is missing, ask the user instead of guessing.
3. Use `make bump-patch`, `make bump-minor`, or `make bump-major` for plain version increments.
4. Only use `make release PART=<type>` when the user explicitly wants changelog/tag release prep rather than a plain bump.
5. Keep this flow separate from releasing to `main` unless the user explicitly combines them.
6. Do not create commits, tags, or push unless the user explicitly asks.
