---
name: address-review
description: Pull PR review comments, implement the requested fixes, and report what was addressed.
---

Use this skill when the user invokes `/address-review`, typically with a pull request number, URL, or branch reference.

When this skill is active:
1. Prefer delegating to the `pr-comment-resolver` custom agent.
2. If the target PR is not clear, ask for the exact pull request reference.
3. Prioritize unresolved review threads over generic comments when the user says "review comments."
4. Group requested changes by file or subsystem and implement them in efficient batches.
5. Run targeted validation for the affected areas and finish with the repository-standard checks that fit the touched files.
6. Do not resolve GitHub threads, merge the PR, or push changes unless the user explicitly asks.
