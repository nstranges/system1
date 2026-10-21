# Ticket writing guide

Rules for writing each ticket's text from its facts record (`data/raw/facts.jsonl`). The record's facts decide the label, so the text must convey them faithfully. A blind reader will later extract the facts from the text alone, using `data/readback/facts_schema.md`.

## Never

- **Never name a queue or team**, or hint at internal routing ("please send this to finance", "escalate to your security team", "this is for sales"). Customers don't know our queues.
- **Never quote or paraphrase the policy**: no "over the $500 limit", no "outside the 30-day window".
- **Never state a fact the record leaves `null`.** A refund with `amount_usd: null` must not mention an amount, and an API error with `api_version: null` must not show a version or a versioned path.
- **Never contradict the customer block.** Plan, region, seats and SSO come from the CRM. Mention them only if a customer naturally would ("we're on the enterprise plan"), and never with different values.
- **Never use real company or person names.** Invent customer business names and staff first names.

## Always

- **Subject line:** 3–10 words, about the main request (`issue_type`).
- **Body length** follows `style.length`:

  | Bucket | Words |
  |---|---|
  | `short` | 40–70 |
  | `medium` | 70–110 |
  | `long` | 110–150 |

- **Make the main request clearly the main one**, both in the subject and in what the customer asks for.
- **Write money in US dollars** with a `$` sign, e.g. `$640` or `$2,300`.
- **Phrase time relatively**, from the customer's point of view on `created_at` day: "yesterday", "12 days ago", "three weeks ago".
  - When `days_since_charge` is between 27 and 33, state it exactly ("29 days ago", "four weeks and three days ago"). "About a month" is too vague.
- **Tone** follows `style.tone`:
  - `calm`: polite and clear.
  - `angry`: frustrated, maybe some capitals or exclamation marks, but no slurs.
  - `terse`: clipped sentences, little greeting.
  - `rambling`: extra backstory and asides, while the needed facts stay in.
- **Typos:** only when `style.typos` is true. Then add 2–4 natural ones (dropped letters, swapped letters, missing apostrophes), never inside an amount, a number of days or an API version.

## Difficulty and style flags

- **`clear`:** state the facts that decide the label plainly, near the start.
- **`borderline`:** state the facts precisely. The values sit close to a threshold, so get the exact number in.
  - If `confusable_with` is set, make the ticket plausibly read like that other kind of request at first glance, while the facts still decide the label. For example, a login problem that sounds alarming but shows no sign of someone else involved, or an EU data request that reads like a general question.
- **`tricky`:**
  - **`secondary_issue` set:** the customer raises that second issue as a separate point, clearly enough to count, usually later in the message.
  - **`implied_facts: true`:** convey the facts that decide the label indirectly but recoverably. For example:
    - "our old v1 integration" or "the `/v1/payments` endpoint" instead of "v1 API"
    - "the annual plan I paid $640 for three weeks back"
  - **`distractor: true`:** include one irrelevant number or date, such as an order number, the size of their team, or an unrelated invoice total.

## Variety

- Vary openings, customer types (agencies, clinics, shops, consultancies, nonprofits, contractors), sign-offs and formatting.
- No two tickets should share an opening sentence.
