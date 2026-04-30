---
name: release-main
description: Guarded release workflow for promoting next to main and watching the release pipeline.
---

Use this skill only when the user explicitly invokes `/release-main` or clearly asks to release or merge to `main`.

When this skill is active:
1. Prefer delegating to the `release-main` custom agent.
2. Confirm the source branch if it is not explicit; in this repository it is usually `next`.
3. Compare the source branch with `main` before taking any write action.
4. Require explicit confirmation before merging or pushing to `main`.
5. Treat push-triggered releases as patch releases by default; if the user wants `minor`, `major`, or `rc`, run the manual GitHub Actions release workflow instead of guessing.
6. Do not deploy unless the user also asked to deploy.
