# Jev (TypeSafe) API: reference notes

Researched 2026-10-20 from docs.typesafe.ai and openrouter.ai. Versions and prices move fast, so re-check the live docs before relying on a limit or a price.

## What Jev is

- TypeSafe's "System One" decision model. It takes a `state` and one or more typed `questions`, and returns typed answers with probabilities. It does not generate text and does not explain itself.
- It cannot be fine-tuned on customer data. Behaviour is shaped only through `state`, question `instructions` and `criteria`. That is the gap sys1 targets.

## Access

| Route | Endpoint | Auth | Model id |
|---|---|---|---|
| TypeSafe direct | `POST https://api.typesafe.ai/v1/systemone` | `Authorization: Bearer $TYPESAFE_API_KEY` | `jev-1.13.0` (pin this), `jev-latest` |
| OpenRouter | `POST https://openrouter.ai/api/v1/systemone` (SDK), or `POST /api/alpha/decisions` | OpenRouter key | `typesafe/jev-1.13`, `~typesafe/jev-latest` |

- `GET /v1/models` lists models and aliases for the account.
- Python SDK: `TypeSafeClient()` (sync) and `AsyncTypeSafeClient()` (async, used with `async with`). Calls look like `client.system_one(state, questions)`.
- SDK env vars: `TYPESAFE_API_KEY` (required) and `TYPESAFE_BASE_URL`.
- To use the SDK through OpenRouter, pass `base_url="https://openrouter.ai/api"`, the OpenRouter key and `model="~typesafe/jev-latest"`.
- Unsloth's docs name the package `typesafe-sdk`. Verify this before installing.
- Retries are configured with `RetryPolicy(max_retries=..., backoff_max=..., timeout=...)`.

## Request

```json
{
  "model": "jev-1.13.0",
  "state": "<ticket text, or a JSON object>",
  "questions": {
    "queue": {
      "type": "choice",
      "instructions": "Which team should handle this ticket?",
      "criteria": {
        "billing_refunds": "Refund requests within policy",
        "billing_disputes": null
      }
    }
  }
}
```

- `state` can be a string, an object or an array.
- `questions` needs at least one entry, keyed by names you choose. Each question is evaluated on its own and in parallel. Extra questions add little latency, but they do add input tokens.
- **choice:** `criteria` is an object with 1–255 options. Each description can be a string, an object, an array or `null`.
- **score:** `criteria` is an ordered array of 1–10 levels, and the array index is the score.
- **noul:** a yes/no question. `instructions` is optional, and the optional `criteria` takes `true` and `false` keys.
- **box:** image bounding box. It needs the `TypeSafe-Danger-Zone-Images` header and isn't relevant to this project.

## Response

```json
{
  "model": "jev-1.13.0",
  "answers": {
    "queue": {
      "type": "choice",
      "choice": "billing_refunds",
      "confidence": 0.7,
      "probabilities": { "billing_refunds": 0.8, "billing_disputes": 0.2 }
    }
  },
  "usage": { "input_tokens": 120, "output_tokens": 12 }
}
```

- `model` reports the versioned id that actually answered, which can differ from the alias sent. Log it with every result.
- **choice:** `choice` is the option with the highest probability.
- **score:** `score` is the probability-weighted *expected* level, not the most likely one. The answer also includes `legend`, `probabilities` and `confidence`.
- **noul:** `noul` is P(true), from 0 to 1. There's no `confidence` field.
- A `422` response carries `detail: [{loc, msg, type}]`.

## Confidence is not calibration

- For choice questions, `confidence = (p_max − 1/n) / (1 − 1/n)`. It depends on the number of options, and Unsloth's server computes it with a different formula.
- **For benchmarks, compute calibration error and any thresholds from `probabilities`, never from `confidence`.**
- The docs don't claim that the probabilities are calibrated.

## Limits and pricing

- **Versions:** `jev-1.13.0` (alias `jev-latest`) is the stable release and the SDK default. `jev-1.14.0` (alias `jev-preview`) was released 2026-10-14. Aliases move without notice.
- **Context:** 64k tokens per request and 32k per question (`state` plus one question). The long-context header raises both to 262k, but it's slower and less accurate, so avoid it.
- **Request body:** at most 32 MiB, sent as UTF-8 JSON. There's no stated limit on the number of questions.
- **Errors to retry:** `429` and `529`. Retry them with exponential backoff, which the SDK does by default.
- **Price:** $0.042 per 1M input tokens, and output is free. A benchmark of 1,000 tickets × 2 prompt conditions costs well under $1.
- **Language:** English gives the best accuracy.

## Known weaknesses (jev-1.13 "jaggedness" page): relevant to task design

- **Option-order bias:** Jev leans toward the first option. Shuffle the option order per case, record it, and use the same order for every model.
- **Literal reading:** scoping words, negations and implied conditions are taken at face value.
- **Multi-hop and compound judgments:** both reduce accuracy.
- **Numbers:** Jev isn't a calculator and can't reliably compare numeric values.
- **Dates:** treated as text, so windows, durations and ordering are unreliable.
- **Irrelevant state:** accuracy drops as `state` fills with unrelated content ("context rot").
- **Score levels:** weak numerical calibration.
- **Prompt injection:** instructions injected into `state` aren't defended against.

## Docs guidance for the "Jev with policy" condition

- Give the full option list, and add an "other" option if some inputs may not fit.
- Make option descriptions distinct from each other. For options that are easy to confuse, use object descriptions, for example with what the option covers, what it excludes and examples. The key names are free-form.
- `instructions` can be a structured JSON object.
- For large taxonomies, chain choice questions level by level.
- The docs don't say where a long policy belongs. That's our call in the design doc.

## Sources

- [System One API reference](https://docs.typesafe.ai/api/system-one.md)
- [Choice primitive](https://docs.typesafe.ai/primitives/choice.md)
- [Confidence](https://docs.typesafe.ai/confidence.md)
- [Models and pricing](https://docs.typesafe.ai/models.md)
- [Request rules and errors](https://docs.typesafe.ai/api/errors.md)
- [Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13.md)
- [Advanced structure](https://docs.typesafe.ai/primitives/advanced.md)
- [Python SDK basic usage](https://docs.typesafe.ai/sdk/python/usage/basic.md)
- [Full docs index](https://docs.typesafe.ai/llms.txt)
- [OpenAPI spec](https://api.typesafe.ai/openapi.json)
- [Jev on OpenRouter](https://openrouter.ai/docs/guides/community/jev)
