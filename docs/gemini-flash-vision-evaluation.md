# Gemini Flash evaluation for label recognition

This is an evaluation only. It does not change the provider used by the wine
or whisky label-recognition flows.

## Recommendation

Try Gemini 2.5 Flash behind a feature flag with a representative set of real
wine-label photos before replacing Claude Haiku 4.5. It should be materially
cheaper and is likely fast enough, but no published benchmark answers the
application-specific question of accurately extracting the required
wine-label fields.

Do not use a personal Gemini app subscription or allowance as the application's
API budget. For a small private deployment, the Gemini API free tier can be
used while its current quota and data-use terms are acceptable; use a billed
Gemini API project for dependable service or stronger data controls.

## Ease of change

The change is contained, but is not a configuration-only model swap:

- Wine calls Anthropic directly from
  `wine_cellar/apps/wine/services/vision_extraction.py`; it has no
  provider-neutral interface.
- The request format must change from Anthropic content blocks to Gemini image
  parts, and the response extraction must change to Gemini's response API.
- Configuration needs a separate server-side `GEMINI_API_KEY`; the existing
  `ANTHROPIC_API_KEY` must remain during a staged rollout.
- The existing prompt, image resizing, field mapping, endpoint, UI contract,
  fallback extraction, and extraction logging can all be retained. Logging
  should record the selected provider/model.
- Wine and whisky have separate vision-service implementations, so both must
  be changed or a shared provider abstraction introduced. The least risky
  first experiment is a Gemini implementation alongside the current provider,
  selected by a setting and covered by the existing endpoint tests.

This is a modest backend change with no expected frontend or database
migration. It should be tested against a labelled image corpus for exact
field extraction, not just whether the API returns valid JSON.

## Capability, speed, and accuracy

Both candidates accept images and can return structured label data from the
existing prompt. Gemini 2.5 Flash supports multimodal input, including images;
Claude Haiku 4.5 supports vision. Neither vendor's general benchmark results
measure this application's required extraction of producer, cuvée, vintage,
origin, grapes, ABV, bottle size, and designation from glare-prone photos.

| Consideration | Gemini 2.5 Flash | Claude Haiku 4.5 |
| --- | --- | --- |
| Image recognition | Multimodal image input; supports structured output | Vision input; current implementation parses prompted JSON text |
| Response format | Can request JSON-schema structured output, reducing parser risk | Current code already works with the text/JSON response |
| Speed | A Flash model designed for low latency; verify with actual three-image scans | The deployed model is also positioned for fast responses |
| Label accuracy | Must be measured locally; use the same images and field-level scoring | Known application baseline; current production behaviour |

For an apples-to-apples trial, retain the current image limit (1568 px), prompt,
and output schema. Send a fixed, consented set of representative front, back,
and barcode images to both providers and measure: successful response rate,
latency, valid structured response rate, and exact/corrected values for each
field. Include small text, curved bottles, glare, non-English labels, and
multi-image submissions.

## Cost

At the published standard API prices, Gemini 2.5 Flash is cheaper for both
input and output tokens:

| Model | Input per million tokens | Output per million tokens |
| --- | ---: | ---: |
| Gemini 2.5 Flash | US$0.30 | US$2.50 |
| Claude Haiku 4.5 | US$1.00 | US$5.00 |

The per-scan saving cannot be derived from those rates alone: providers count
image tokens differently, and the current request allows up to three images
and 2,048 output tokens. For the same counted input/output tokens, Flash is
70% cheaper on input and 50% cheaper on output. Measure token usage from real
requests before projecting monthly cost; output length and image tiling are
the main variables. Batch pricing is irrelevant to the interactive scan flow.

Prices and quotas change, so confirm them before implementation:

- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Anthropic API pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

## Personal/free Google allowance

There are two different products:

1. A personal Gemini app plan/allowance is for the consumer Gemini product; it
   is not an API credit entitlement and cannot be used by this server.
2. The Gemini API has a separate free tier, accessed with an API key from a
   Google project. It can suit a private, low-volume experiment, subject to
   the model's current request/token limits and the Gemini API terms.

Do not put a browser-exposed or personal key in the client: keep the API key
in server environment configuration. Free-tier availability is not a service
guarantee, and Google states that free-tier content may be used to improve its
products; that is a privacy trade-off for label photos. Enable billing and use
the paid Gemini API tier before relying on the feature, particularly if scans
may contain personal information or the service is shared beyond a private
household.

Relevant Google documentation:

- [Gemini API billing](https://ai.google.dev/gemini-api/docs/billing)
- [Gemini API terms](https://ai.google.dev/gemini-api/terms)
- [Gemini API pricing and free-tier data use](https://ai.google.dev/gemini-api/docs/pricing)

## Decision gate

Replace Haiku only if the trial demonstrates comparable or better
field-level accuracy, acceptable p95 interactive latency, reliable quota headroom,
and a privacy posture acceptable for uploaded label images. Otherwise retain
Haiku 4.5; its existing integration avoids provider migration risk.
