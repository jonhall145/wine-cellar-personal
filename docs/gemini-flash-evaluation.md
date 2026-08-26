# Gemini Flash Evaluation for Copilot Cloud Agent

**Scope:** This evaluates the model used by GitHub Copilot's cloud/coding agent, not
the application's Anthropic-backed wine-label extraction service. No application
provider, API key, dependency, or runtime configuration change is proposed.

**Reviewed:** 2026-08-26

## Recommendation

Trial **Gemini 3.7 Flash** for small and repetitive coding tasks if the model picker
is available on the Copilot plan. It is a like-for-like option with Claude Haiku 4.5,
has the same GitHub-stated task fit, and is currently cheaper per token. Keep Claude
Haiku 4.5 as the baseline and compare completed-task quality and elapsed time over a
small set of representative issues before making it the default.

The Gemini 3.7 Flash price is promotional through 2026-12-31, so reassess it before
then. For a task where the picker is unavailable, or where predictable cost and
reliability matter more than choosing a particular model, use **Auto**; GitHub says
Auto applies a 10% model-cost discount on paid plans and selects based on task,
availability, and system health.

## Ease of Change

There is no repository change to make. Claude Haiku 4.5 and Gemini 3.7 Flash are
both selectable in the Copilot cloud-agent model picker when starting a supported
task. Choose the model while assigning an issue to Copilot, mentioning `@copilot` in
a pull-request comment, or starting a task from a supported agent entry point. When
no picker is shown, Copilot uses Auto.

The selection remains subject to the account's Copilot plan and any organization
policy. It does not change this repository's code, CI, secrets, or the separate
Anthropic API integration used for label scanning.

## Capabilities and Speed

GitHub categorizes both **Claude Haiku 4.5** and **Gemini 3.7 Flash** as suited to
"fast help with simple or repetitive tasks" and says both excel at "fast, reliable
answers to lightweight coding questions." Neither GitHub comparison provides
comparable latency or benchmark figures, so there is no supported claim that one is
faster or more accurate for this repository.

Use a trial to measure the outcomes that matter here:

1. Give each model comparable small bug fixes, documentation updates, and focused
   test changes.
2. Record elapsed time, number of follow-up prompts, test results, and review
   findings.
3. Retain the model that completes the work more reliably at an acceptable cost.

## Cost

GitHub prices Copilot usage in AI credits from input, cached-input, and output tokens
(one AI credit is USD $0.01). The following rates are USD per one million tokens:

| Model | Input | Cached input | Output |
| --- | ---: | ---: | ---: |
| Claude Haiku 4.5 | $1.00 | $0.10 | $5.00 |
| Gemini 3.7 Flash | $0.75 | $0.075 | $3.75 |

At these current rates, Gemini 3.7 Flash is 25% cheaper for each listed token type.
Claude Haiku 4.5 also has a $1.25-per-million cache-write rate; GitHub's Gemini
table does not list a cache-write rate. The Gemini rates are promotional and expire
on 2026-12-31, so they are not a long-term price guarantee. Actual task cost depends
on the token mix and is offset by any included plan allowance.

## Personal Google Free Allowance

**No, not for Copilot cloud-agent tasks.** A personal Google AI Studio key or free
Gemini API allowance cannot be used to pay for, or extend, GitHub Copilot's cloud
agent. Cloud-agent use is covered by the GitHub Copilot plan's included AI credits,
then GitHub's additional-usage billing where enabled.

GitHub supports personal bring-your-own-key (BYOK) only in specific local clients:
VS Code, JetBrains, Xcode, Copilot CLI, the GitHub Copilot app, and the Copilot SDK.
That is separate from a cloud-agent task on GitHub and would be a local development
workflow decision rather than a repository setting.

## Sources

- [Changing the AI model for GitHub Copilot cloud agent](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/changing-the-ai-model)
- [AI model comparison](https://docs.github.com/en/copilot/reference/ai-models/model-comparison)
- [Models and pricing for GitHub Copilot](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing)
- [About Copilot auto model selection](https://docs.github.com/en/copilot/concepts/models/auto-model-selection)
- [Bring your own key for GitHub Copilot](https://docs.github.com/en/copilot/concepts/models/bring-your-own-key)
