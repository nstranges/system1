# Ticket facts schema

Each ticket is a JSON object with two parts:
- `ticket`: the customer's message, with `subject`, `body` and `created_at` (the date the ticket arrived, `YYYY-MM-DD`).
- `customer`: four account fields from the CRM.

For each ticket, record the nine facts below.

## About the product

Tallyfern is an invoicing and payments platform for small and mid-sized businesses. Customers pay Tallyfern subscription fees, send invoices to their own clients, collect payments, and receive **payouts** of the money they collected into their bank account. Developers integrate through the Tallyfern API:
- **v1** is the older, legacy version. Its endpoints look like `/v1/...`.
- **v2** is the current version. Its endpoints look like `/v2/...`.

## Fields from the `customer` block

Copy these as given, with basis `metadata`.

| Field | Source | Values |
|---|---|---|
| `plan_tier` | `customer.plan` | `free`, `starter`, `pro`, `enterprise` |
| `region` | `customer.region` | `us`, `ca`, `eu`, `uk`, `apac` |
| `seats` | `customer.seats` | integer |
| `sso_enabled` | `customer.sso_enabled` | `true` or `false` |

## Fields from the message

### `issue_type`

The customer's **main** request: what they mainly want Tallyfern to do or answer. It's usually what the subject line is about. Pick exactly one value:

| Value | Meaning |
|---|---|
| `refund_request` | Wants money back for something Tallyfern charged them (subscription, upgrade, fees). |
| `chargeback_dispute` | A chargeback or dispute has been filed with a bank or card issuer, by the customer or by one of their own payers. |
| `billing_question` | A question about a charge or invoice, updating a card, or tax details, without asking for money back. |
| `failed_payout` | A payout of the customer's own money to their bank account failed, is late, or arrived short. |
| `login_problem` | Can't sign in: password, two-factor codes, a locked account or single sign-on, with no sign that someone else is involved. |
| `api_error` | Errors or unexpected responses from the Tallyfern API in the customer's integration. |
| `data_request` | Asks for a copy of their data, or for their data to be deleted. |
| `outage_report` | Says Tallyfern itself is down or broadly failing: dashboard not loading, all payments failing, every API call erroring. |
| `security_concern` | Suspects someone else accessed or changed the account, fraud, unauthorized invoices or payments, or phishing imitating Tallyfern. |
| `plan_change` | Wants to change plan or the number of seats. |
| `how_to` | Asks how to do something in Tallyfern. |

### `secondary_issue`

A second, **distinct** request or report in the same ticket, using the same values as `issue_type`. Use `null` if there's none. Background detail that supports the main request doesn't count. Only something the customer separately raises does.

### `amount_usd`

The amount of money the main request is about (the charge to refund, the disputed amount, the payout), as a number in US dollars, e.g. `640` or `2300.5`.
- Ignore other numbers that appear in passing.
- Use `null` if the message doesn't give the amount for the main request.

### `days_since_charge`

How many days before `created_at` the charge in the main request was made, as an integer. Use `null` if the main request isn't about a charge, or if the message doesn't say when it was made. Conversions:

| Phrase | Days |
|---|---|
| "today" | 0 |
| "yesterday" | 1 |
| "N days ago" | N |
| "N weeks ago" | 7 × N |
| "a month ago" | 30 |
| "two months ago" | 60 |
| "N weeks and M days ago" | 7 × N + M |

- For an absolute date such as "charged on September 3", count the days from that date to `created_at`.
- Vague phrases ("a while ago", "recently", "some time back") count as not stated: use `null` with basis `not_stated`.

### `api_version`

Which API version the integration in the message uses:
- `v1` if the message names v1, shows `/v1/` paths, or calls it the legacy or old API.
- `v2` if it names v2 or shows `/v2/` paths.
- `null` if it doesn't say, or the ticket isn't about the API.
