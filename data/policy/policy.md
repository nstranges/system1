# Tallyfern Support Triage Policy

Internal guide for routing inbound support tickets. Version 1.0, October 2026.

Tallyfern is a fictional invoicing and payments platform for small and mid-sized businesses. Customers send invoices, collect card and bank payments, receive payouts to their bank account, and integrate through our REST API. Our legacy **v1** API is still supported for older integrations, and **v2** is current.

Every ticket goes to exactly one queue and gets one priority (P1 is highest). Work through the routing rules **in order** and stop at the first rule that matches. Then apply the priority rules the same way.

## What the agent sees

Each ticket shows the customer's message (subject, body and the date it was created), plus four account fields from our CRM:

- **Plan:** `free`, `starter`, `pro` or `enterprise`.
- **Region:** `us`, `ca`, `eu`, `uk` or `apac`.
- **Seats:** the number of user seats on the account.
- **SSO enabled:** whether the account signs in through single sign-on. Only enterprise accounts can enable SSO.

Everything else (what the customer wants, amounts, how long ago they were charged, which API version they use) comes from the message itself.

## Unknown means no

If the message doesn't tell you a fact a rule depends on, treat the condition as **not met**. Tier 1 will ask the customer for details. For example:
- A refund request that doesn't give an amount isn't "over $500".
- An API error that doesn't say which version isn't a v1 error.

## Routing rules

The first three rules are **overrides**. They apply when the customer raises the issue anywhere in the ticket, even as a side note to a different main request. Every later rule looks only at the customer's **main** request.

### R01: Account security → `trust_safety`

The customer reports, or strongly suspects, account compromise, fraud or unauthorized activity: someone else logging in, payouts redirected to an unknown bank account, invoices sent that they didn't create, or phishing that imitates Tallyfern. This takes precedence over everything else.

> *Example:* "I can't log in, and I got an email saying my payout bank details were changed. I didn't do that." → `trust_safety` (R01), even though it starts as a login problem.

### R02: Service outage → `incident_response`

The customer reports that Tallyfern itself is down or broken for them broadly: the dashboard won't load, payments are failing across the board, or the API is returning errors for every request. One failed invoice or a single bug isn't an outage.

> *Example:* "Since 9am none of our team can load the dashboard and checkout pages show an error." → `incident_response` (R02).

### R03: Chargeback or bank dispute → `billing_disputes`

The customer mentions that a chargeback or a dispute has been filed with a bank or card issuer, either by them against a Tallyfern charge or by one of their own payers. This applies even if their main request is a refund.

> *Example:* "Please refund last month's charge. I've also opened a dispute with my bank in case." → `billing_disputes` (R03).

### R04: Large or late refund → `finance_review`

The main request is a refund of a Tallyfern charge, **and** either:
- the amount is **more than $500**, or
- the charge was **more than 30 days** before the ticket.

> *Examples:*
> - "Refund the $640 annual upgrade from last week" → `finance_review` (R04, over $500).
> - "Refund the $120 charge from 45 days ago" → `finance_review` (R04, outside the window).

### R05: Standard refund → `billing_refunds`

Any other refund request: **$500 or less**, charged **30 days ago or less**, or with the amount or timing not given.

> *Examples:*
> - "Refund the $500 charge from 30 days ago" → `billing_refunds` (R05). Exactly $500 and exactly 30 days are still standard.
> - "Refund the $500.01 charge from yesterday" → `finance_review` (R04).

### R06: Failed or missing payout → `payments_ops`

The customer's own payout to their bank account failed, is late or arrived short.

> *Example:* "Our payout of $2,300 due Friday never arrived." → `payments_ops` (R06).

### R07: Legacy API error → `legacy_api`

The customer reports an API error, **and** the integration uses the **v1** API.

> *Example:* "Our old v1 integration started returning 401s this morning." → `legacy_api` (R07).

### R08: API error → `api_support`

Any other API error: on v2, or with the version not given.

> *Examples:*
> - "POST /v2/invoices returns a 422." → `api_support` (R08).
> - "The API is rejecting our webhook signature." → `api_support` (R08, version not given).

### R09: Enterprise SSO sign-in → `enterprise_identity`

The customer can't sign in, **and** the account is on the **enterprise** plan with **SSO enabled**.

> *Example:* Enterprise account with SSO: "Half our staff get bounced back to the login page after the identity provider step." → `enterprise_identity` (R09).

### R10: Sign-in problem → `account_access`

Any other sign-in problem: forgotten password, two-factor codes not arriving, a locked account. This includes enterprise accounts that don't use SSO.

> *Examples:*
> - Pro account: "I never receive my 2FA code." → `account_access` (R10).
> - Enterprise account without SSO, same message → `account_access` (R10).

### R11: EU/UK data request → `privacy_legal`

The customer asks for a copy of their data, or for their data to be deleted, **and** the account region is **eu** or **uk**. These requests have legal deadlines.

> *Examples:*
> - Region `eu`: "Please delete all data you hold on our company." → `privacy_legal` (R11).
> - Region `us`, same message → `general_support` (R13).

### R12: Larger plan change → `sales`

The customer wants to change plan or seat count, **and** the account has **50 or more seats** or is on the **enterprise** plan.

> *Examples:*
> - 50 seats on pro: "We'd like to add 20 more seats." → `sales` (R12).
> - 49 seats on pro, same message → `general_support` (R13).

### R13: Everything else → `general_support`

Billing questions (how an invoice was calculated, updating a card, tax fields), how-to questions, data requests outside the EU and UK, and plan changes on smaller accounts.

> *Example:* "How do I add our VAT number to invoices?" → `general_support` (R13).

## Priority rules

Apply these in order and stop at the first match:

1. **P1**: the ticket was routed by R01 (account security).
2. **P1**: the ticket was routed by R02 (outage) and the account is on the enterprise plan.
3. **P2**: any other R02 outage.
4. **P2**: an R06 payout problem of **$10,000 or more**. One of $9,999 is P3.
5. **P2**: an R09 enterprise SSO sign-in problem.
6. **P4**: tickets routed by R12 (sales) or R13 (general support).
7. **P3**: everything else.

## Queues at a glance

| Queue | Team | Rule |
|---|---|---|
| `trust_safety` | Trust & Safety | R01 |
| `incident_response` | Incident Response | R02 |
| `billing_disputes` | Billing Disputes | R03 |
| `finance_review` | Finance Review | R04 |
| `billing_refunds` | Billing Refunds | R05 |
| `payments_ops` | Payments Operations | R06 |
| `legacy_api` | Legacy API | R07 |
| `api_support` | API Support | R08 |
| `enterprise_identity` | Enterprise Identity | R09 |
| `account_access` | Account Access | R10 |
| `privacy_legal` | Privacy & Legal | R11 |
| `sales` | Sales | R12 |
| `general_support` | General Support | R13 |
