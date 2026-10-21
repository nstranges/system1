# system1 plan: prove it on a benchmark, then build the product

Oct 20, 2026 · Thomas Michalski and Nicholas Stranges · Status: draft for approval

## Why we're doing this

General decision models such as Jev are fast and cheap, but they only know a team's rules if someone pastes the rules into every request, and they can't be fine-tuned. Our bet is that a small model trained on a team's own decisions ("sys1", a LoRA on Laya) beats Jev on that team's work, at similar speed and cost, behind the same API.

We prove or disprove that on a benchmark first. The product pieces (asking a person about uncertain cases, retraining, the app) only matter if the benchmark shows sys1 can win, so they wait for the result.

## Phases at a glance

| Phase | What it answers | Starts when |
|---|---|---|
| **1. Benchmark** | Does sys1 beat Jev on a company-specific triage task? | Now |
| 2. Learn from a person | Does asking a person about ~20 uncertain tickets make sys1 better? | Phase 1 is promising (see the decision gate) |
| 3. Product | Can a real user use it? The B2B website, gateway and onboarding agent, specified in the [product design](2026-10-21-system1-product-design.md) | Thu Oct 22, alongside phase 1 (decided Oct 21) |
| 4. Scale and stretch | API-generated data at scale, MCP, sponsor integrations | Only if time allows |
| Submission | Demo video (4 minutes or less), Devpost write-up, links | Always, by Oct 25, 23:59 ET |

Phase 1 is specified in detail below. Phases 2–4 are outlined only and get their own design when we reach them.

## Goals, non-goals and anti-goals (phase 1)

**Goals**
- A labelled dataset of about 500 support tickets for one fictional company, with the policy that defines the correct answers.
- sys1 trained on it.
- One honest results table comparing sys1, base Laya, Jev with only the label list, and Jev with the full policy, on tickets that no model trained on.
- A clear decision about what to do next.

**Non-goals for phase 1:** the web app, the review queue, retraining, serving sys1 behind an endpoint, MCP, sponsor integrations, languages other than English, and images.

**Anti-goals.** Any of these makes the result worthless, even if sys1 "wins":
- Jev isn't given the policy in the comparison that counts.
- Any model is trained, calibrated or prompt-tuned on the test tickets.
- Gold labels come from Claude's judgment instead of the written rules.
- Real or confidential customer data enters the repo.
- Anthropic API credits are spent on data generation in this phase.

## Constraints

- **Dates:** submission is due Sun Oct 25 at 23:59 ET, and Demo Day is Oct 29. Today is Tue Oct 20.
- **Data budget:** about 500 tickets for now, written by Claude inside an agent session, not through the Anthropic API. More tickets will probably be added later, and the design must allow that.
- **Laya's input window:** 512 tokens for the root checkpoint (to verify; see "Verify early"). Questions and options are kept and the end of the ticket is cut, so tickets must be short and the option descriptions sys1 sees must be terse.
- **Option count:** Laya loses to Jev above about 20 options, so the queue question has at most 15 options.
- **Jev:** pinned to `jev-1.13.0`. Its limits are 64k tokens per request and 32k per question, which is ample. It costs $0.042 per 1M input tokens.
- **Training:** Modal, L4 GPU, Unsloth `FastDecisionModel`, built on the existing [train.py](../../../train.py).

## Phase 1 design

### 1. The company and its policy

- **Company:** a fictional B2B invoicing and payments SaaS for small and mid-sized businesses. Choose a name that doesn't belong to a real company. This domain naturally has money amounts, time windows, plan tiers, API versions, regions and outages.
- **Policy document** (`policy.md`): about 13 queues (15 at most), each defined by explicit, ordered routing rules over ticket facts. It should read like a real internal triage guide.
- **Priority:** the policy also defines priority levels P1–P4. Priority gold is computed and stored for every ticket, but the headline benchmark is the queue question only. Whether to benchmark priority is decided after the queue results.
- **Rule types.** Use a realistic mix that includes the kinds Jev's docs say it handles poorly:
  - money thresholds, e.g. "refunds over $500 go to Finance Review"
  - time windows, phrased the way customers phrase them ("three weeks ago", "back in July")
  - conditions that combine facts, e.g. "enterprise plan *and* SSO login problem → Enterprise Identity"
  - version-specific routing, e.g. API v1 → Legacy team
  - region-specific routing, e.g. EU data-deletion requests → Privacy & Legal
  - overrides with explicit precedence, e.g. "any sign of account compromise → Trust & Safety, whatever else the ticket is about"
- **Avoid rules that need exact date arithmetic between two explicit dates.** No model here can learn those from 300 examples, so they would only add noise.
- **Illustrative queue set** (final list chosen in the policy step): trust_safety, incident_response, billing_disputes, finance_review, billing_refunds, payments_ops, legacy_api, api_support, enterprise_identity, account_access, privacy_legal, sales, general_support (the fallback).

### 2. Ticket facts and gold labels

- Every ticket starts as a **facts record**, for example: plan tier, region, seat count, primary issue type, optional secondary issue, amount, how long ago the charge happened, API version, whether SSO is on, outage indicators, security indicators, whether a chargeback was filed. The exact schema is set in the policy step.
- **The gold queue and priority are computed by code** (a small deterministic rules function that mirrors `policy.md`) from the facts. Claude never assigns a label by judgment.
- **The facts that decide the label must be recoverable from the ticket.** Other facts may be left out.
- **What a model sees (`state`):** the ticket's subject, body and created date, plus a small customer-metadata block (plan tier, region, seats), the way a helpdesk shows CRM fields. Rules can then depend on plan or region without every customer announcing them. Target total size is about 300 tokens or less, to leave room for the options in Laya's window.

### 3. Writing the tickets

- A seeded script builds the facts grid with the exact coverage we want:
  - every queue represented, with at least 25 tickets per queue in the final set
  - a difficulty mix of about 50% **clear**, 30% **borderline** and 20% **tricky**:
    - clear: one issue, facts stated plainly, nowhere near a threshold
    - borderline: within about 10% of a money threshold or a few days of a window, or sitting between two easily confused queues
    - tricky: facts implied rather than stated, two issues where precedence decides, or irrelevant distracting details
- Generate about 550 to end with at least 500 after the read-back and duplicate checks.
- Claude writes each ticket's text from its facts record, in batches, inside an agent session.
- **Variety:** tone (calm, angry, terse, rambling), length (about 40–200 words), typos, and customer types.
- **Ticket text must never name a queue** or quote the policy.
- **Saved as:** raw facts and tickets as JSONL (the source of truth, committed). The built dataset is written as parquet.

### 4. Read-back check

- A reader that did not write the tickets sees only each ticket's `state` and the facts schema. It extracts the facts. It never sees the intended facts or the policy.
- The extracted facts are compared with the intended facts that decide the label. If they don't match, the ticket is rewritten once. If it still doesn't match, it's dropped.
- **The reader is a fresh agent** with no memory of writing the tickets. Thomas runs it in a separate session, using the prompt in `agent-prompts/readback-check.md` (gitignored).
  - The agent gets only `data/readback/tickets_blind.jsonl` (ids and `state`) and `data/readback/facts_schema.md`, copied into an empty folder outside the repo.
  - It returns `extracted.jsonl`, with a value, a basis (`metadata` / `stated` / `implied` / `not_stated` / `conflicting`) and an evidence quote for every fact, plus flags for tickets that name a queue, raise several issues, or read as unrealistic.
- **So the dataset step must produce** the blind file and a schema doc a stranger can apply. The comparison script must accept `implied` as a match, and treat `not_stated` or `conflicting` on a fact that decides the label as a failure.

### 5. Building the dataset and splitting it

- **Duplicates:** drop near-duplicate tickets before splitting. The builder picks the similarity method.
- **Split:** 300 train / 50 calibration / 150 test, stratified by queue and difficulty, with a fixed seed.
- **The test set is frozen.** No training, calibration, prompt tuning or ticket rewriting may use it.
- **Adding tickets later:** existing test tickets stay in the test set forever. New tickets are split by the same proportions, unless we decide otherwise at that point.
- **Each row holds:**
  - `id`, `split` and `difficulty`
  - the facts record and the rule that decided the label
  - `state`
  - two question variants, terse and policy (next section)
  - `gold` for queue and priority
  - the ticket's option order

### 6. Two versions of the question

- **Terse:** a queue choice question with each option's key and a description of 10 words or fewer. **sys1, base Laya and "Jev with only the label list" all see exactly this.** That makes the sys1-versus-Jev comparison the same input to two different models.
- **Policy:** the same option keys, but each description carries that queue's rules (what it covers and what it excludes), and the instructions state the precedence order. **Only "Jev with policy" sees this.** It's Jev's best shot, written following Jev's own prompting guidance.
- **Option order:** shuffled per ticket with a seed and stored in the row. Every model gets the same order for the same ticket, because Jev favours whichever option comes first.

### 7. Models under test

| Row | Model | Question variant | Trained on our data |
|---|---|---|---|
| A | Jev `jev-1.13.0` | terse | no |
| B | Jev `jev-1.13.0` | policy | no (**this is the bar**) |
| C | base Laya | terse | no |
| D | sys1 (Laya + LoRA) | terse | yes, 300 train tickets |
| E (optional) | Claude with the policy, as a fresh agent | policy | no. A ceiling that shows how hard the tickets are |

Jev's prompt for row B may be tuned on the calibration split only. Log raw responses, including the `model` field Jev returns.

### 8. Training sys1

- Generalise `train.py` to:
  - train on our parquet file's train split
  - calibrate on the calibration split
  - predict every test ticket and save the full probability distribution for each
- Use 3–4 epochs, as Unsloth recommends for small datasets.
- Train with **3 seeds** and report the mean and the spread. With 300 examples, one run can be lucky.
- **Learning curve:** also train on 100 and 200 tickets. The trend tells us whether adding tickets is worth it.
- Base Laya (row C) predicts the same test tickets with no training.

### 9. Metrics and the results report

All of these are computed on the 150 test tickets:
- **Accuracy and macro-F1**, with 95% bootstrap confidence intervals.
- **sys1 against Jev with policy:** the accuracy difference, with a paired 95% confidence interval. This is the headline number.
- **Accuracy by difficulty and by rule type.** This is where the story is.
- **The most common confusions between queues.**
- **Calibration error,** computed from `probabilities`, never `confidence`. Report it raw and after fitting a temperature on the calibration split, for every model, to keep the comparison fair. With 150 tickets it's a rough signal, and the report should say so.
- **Latency per decision.** For Jev this is wall-clock time including the network. For sys1 it's forward-pass time on the L4. The report states the difference.
- **Cost per 10,000 decisions.** For Jev, use logged input tokens × price. For sys1, use measured GPU-seconds × the current Modal L4 rate, looked up at the time.

Output: `docs/results/phase1-benchmark.md`, with the table, a learning-curve chart and short findings.

### 10. Decision gate (end of phase 1)

| Result | Next step |
|---|---|
| sys1 beats Jev with policy and the paired interval excludes zero (with 150 tickets, roughly an 8+ point gap) | Go to phase 2 on this task. The benchmark becomes the core of the demo |
| Inconclusive (interval includes zero) | Look at the learning curve. If it's still rising, add tickets (to 1,000+) before changing anything else. Consider Qwen3.5-2B as the base model |
| Jev with policy clearly wins | Find out why: cut-off tickets, too few examples, or rule types sys1 can't learn. Fix one thing and rerun. If it still loses, report that honestly and pitch speed, cost and self-hosting |

## Later phases (outline only)

- **Phase 2, learn from a person:**
  - sys1 scores a pool of new unlabelled tickets, and the person answers the ~20 it's least sure of.
  - Each answer is expanded into variants. Whether that uses the Anthropic API gets revisited here.
  - sys1 retrains.
  - Headline chart: test accuracy after 0, 20 and 50 answers, on the same frozen test set.
- **Phase 3, product:** replaced by the [product design](2026-10-21-system1-product-design.md) (Oct 21).
- **Phase 4, scale and stretch:**
  - Anthropic API generation for thousands of tickets
  - Qwen3.5-2B as the base model
  - Clerk, Era by Eon, SurrealDB Agent Memory and MCP have moved to the product design's tiers and roadmap.
- **Submission:**
  - the demo video (4 minutes or less)
  - the Devpost write-up, disclosing the Modal/Unsloth experiments from before the build week and any templates used
  - the public repo, and a live endpoint if phase 3 exists

## Timeline

| Day | Work |
|---|---|
| Tue Oct 20 | Approve this design. Write the implementation plan. Draft the policy and the facts schema. Get a Jev key |
| Wed Oct 21 | Build the facts grid and rules function. Write about 550 tickets. Run the read-back and build the dataset. Generalise `train.py` in parallel |
| Thu Oct 22 | Train sys1 (3 seeds plus the learning curve). Run Jev and base Laya. Write the results report |
| Fri Oct 23 | Decision gate. Start phase 2 or 3 depending on results |
| Sat Oct 24 | Polish whatever the demo shows. Record the video |
| Sun Oct 25 | Buffer. Submit on Devpost by 23:59 ET |

## Ownership (phase 1, proposed)

- **Thomas, with Claude:** policy, facts grid, tickets, read-back, dataset build, the Jev benchmark runs and the results report.
- **Nicholas:** generalise `train.py`, run sys1 training (seeds and learning curve), calibration, and sys1's test predictions.

## Risks

| Risk | Plan |
|---|---|
| Laya's 512-token window cuts tickets or options | Keep `state` at about 300 tokens or less and terse descriptions short. Verify the real window first |
| 300 training tickets is too few | The learning curve shows it. Add tickets and keep the test set frozen |
| The same model wrote the policy and the tickets, so the writing style may make the task easier for a model trained on it | Vary style deliberately, run the read-back, and say so in the report |
| 150 test tickets gives wide confidence intervals | Report the intervals. Grow the test set when tickets are added |
| Ticket text gives the answer away | Writing rule: never name a queue. Spot-check during the read-back |
| No Jev key on Wednesday | Get one on Tuesday, from TypeSafe directly or through OpenRouter |

## Verify early (unconfirmed facts)

- The real input window `train.py` trains and predicts at (512 vs 2,048), and whether ~13 terse options plus a ~300-token ticket fit without cutting.
- **Why our typed-decisions LoRA scores 0.658** when published fine-tuned Laya scores about 0.77. Check the learning rate, the epoch count and the `trainable.pt` save and load path before training sys1 on our data. Details are in [laya-unsloth.md](../../reference/laya-unsloth.md).
- ~~Whether `predict` returns per-option probabilities~~. Verified: Nicholas's eval scripts use them.
- ~~The Jev access route~~. Verified: TypeSafe direct (`api.typesafe.ai`) works with our key, and `eval_jev.py` uses plain HTTP, so no SDK is needed.

## Existing code to build on

Nicholas's eval harness already covers most of what phase 1's benchmark needs. Phase 1 points it at our dataset instead of writing a new one:
- `eval_common.py` scores every model the same way, using accuracy, ECE and NLL computed from probabilities.
- `eval_jev.py`, `eval_laya.py` and `eval_lora.py` correspond to rows A/B, C and D.
- The `Makefile` wraps them: `make eval-jev`, `make eval-laya`, `make eval-lora`, plus `LIMIT=` for smoke tests.

Still missing: loading our parquet file, the terse and policy question variants, macro-F1, the bootstrap intervals, accuracy broken down by difficulty and rule type, latency and cost.

## Decision log

**Decided by Thomas:**
- Support-ticket triage as the use case.
- Benchmark first, before the review loop.
- Synthetic data with no hand-labelling.
- A three-way split.
- The benchmark rows: Jev with labels only, Jev with policy, base Laya and sys1.
- Gold labels computed from written rules.
- Fewer queues (about 15 at most).
- Generation inside an agent session, not through the Anthropic API.
- 500 tickets for now, probably more later.

**Claude's calls**, open to change:
- The 300/50/150 split.
- An invoicing and payments SaaS as the fictional company.
- About 13 queues.
- Priority stored but not the headline.
- Customer metadata included in `state`.
- The 50/30/20 difficulty mix.
- Generating about 550 to keep at least 500.
- 3 seeds plus a learning curve.
- Row E as optional.
- The report's location.
- The phase 1 ownership split.

## Left to the builder

File and module layout, script structure, the duplicate-detection method, training hyperparameters beyond the epoch guidance, Jev request concurrency, calibration binning, and chart tooling.
