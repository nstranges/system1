# system1 product: from your rules to your own decision model

Oct 21, 2026 · Thomas Michalski and Nicholas Stranges · Status: direction agreed Oct 21. The implementation plan gets written with Thomas before building starts.

This expands phase 3 of the [plan](2026-10-20-system1-plan-design.md) and pulls in parts of phases 2 and 4. Phase 1 (the benchmark) is unchanged and still comes first.

## The product in one paragraph

Teams make the same decision hundreds of times a week: which queue a ticket goes to, whether a refund gets approved, which rep gets a lead. system1 is a website where a team lead describes one of those decisions, and an agent helps them turn it into three things:
- written rules
- a working decision endpoint (Jev with their rules attached, live in minutes)
- their own fine-tuned model (sys1), which learns their rules and keeps improving from their corrections

Pitch line: **"Jev knows decisions. Your model knows *your* decisions."**

## Who it's for

system1 is a B2B product, sold self-serve first. One person at a company signs up free, gets value from the Quick lane, and the team pays for trained models and volume. The UI is friendly because the buyer is an operations lead, not a developer.

- **Who it's for:** any team with a decision it makes again and again, using rules in a doc that nobody applies consistently. They know the rules, but they don't write code or know what a LoRA is. Support-ticket triage is the first use case and the flagship demo (Tallyfern triage); refund approvals, lead routing and policy checks have the same shape.
- **Expansion:** other operations decisions at the same companies, such as refunds, lead routing and expense checks. Same buyer, more projects.
- **Channel:** consultants, agencies and developers who build automations for clients. They use the API now, and the MCP server later (see Roadmap).
- **Free tier:** individuals and hobbyists can use the Quick lane. They're not part of the pitch.
- **Long-term reach:** the same engine works for any team with a repeated decision. The pitch stays on one user, as the hackathon brief asks: *"Not 'everyone who does X.' A single person, team, or workflow you can point to."*

## The hackathon and how we score

[Build North: Ship Something Real](https://build-north.devpost.com/), hosted by Georgian, Anthropic, Google Cloud for Startups, TAPNET, Expo, Clerk, Eon and SurrealDB, and tagged Enterprise. The judges are:
- Georgian's lead investor
- Georgian's CTO
- a former VP of AI Engineering at the Vector Institute
- a Google customer engineer for startups

| Criterion (Devpost wording) | What we show |
|---|---|
| **Innovation:** going beyond the obvious | A model per team, trained from its own written rules using rule-labelled synthetic data. Answers that cite the rule behind them (S5) |
| **Real-world impact:** clear user, value-add, path to production | A clear user (a team that owns a repeated decision), a benchmark on one such decision, and a Jev-compatible API, so adoption is a URL change |
| **UI & design:** usable by a real user | An agent with clickable answers next to an editable canvas, in plain words |
| **Tech & deployment:** solid architecture, deployed, serving | Live on Modal, with the gateway serving Jev and sys1, a model registry, and tests |
| **Security & ethics:** guardrails, safe handling of user data | Clerk sign-in, hashed keys, separation between projects, a click to confirm before any spend, human review for unsure decisions, no training on Jev output, a frozen test set, an audit log of every decision, and declining high-stakes uses |

- **Submission:**
  - a public GitHub repo
  - a live link
  - a demo video of **4 minutes or less**
  - a write-up covering the stack and the partner platforms used
  - the team
  - a disclosure of prior work, templates *and AI tools used*
- **Demo Day:** the top 10 are announced Oct 26 and demo live in Toronto on Oct 29. At least one of us must attend in person.
- **Category prizes:**
  - **Clerk:** in V1.
  - **Eon:** V2, using Era by Eon to test the agent.
  - **SurrealDB Agent Memory:** V3, if there's time.
  - **Expo:** doesn't apply, because we're not building a mobile app.

## Goals, non-goals and anti-goals

**Goals (hackathon)**

- A deployed website where a judge can go from "I have a decision" to "I have rules and a working endpoint" in a few minutes, with an agent guiding them.
- The flagship project (likely Tallyfern triage) shown end to end: rules, examples, trained sys1, an honest comparison with Jev, a live endpoint and feedback capture.
- Sign-in with Clerk, which also qualifies for the Clerk category prize.
- A Claude Skill that walks a company through the same onboarding inside Claude Code.
- One Jev-compatible endpoint (`POST /v1/systemone`) that serves Jev-with-your-rules, sys1, or both.

**Non-goals (hackathon):**
- billing
- team accounts and roles
- real customer data
- languages other than English
- images
- letting users train arbitrary base models
- the Claude connector and MCP server (see Roadmap)

**Anti-goals.** Any of these makes the product a failure, even if it works:

- A results screen that hides it when Jev with the user's rules beats sys1.
- Demo footage that shows pre-recorded or faked steps as if they were live. The hackathon rules also forbid "faking your demo".
- Spending money (example generation, GPU training) without the user clicking to confirm.
- Feedback on test-set items flowing into training. The test set stays frozen.
- Jev's answers used as training labels, or used to choose which examples get labelled (TypeSafe §2.3b).
- A screen that reads like an ML tool (losses, epochs, LoRA rank) to a non-technical user.
- Product work delaying phase 1's read-back, training or results report.

## Constraints

- **Dates:** submission Sun Oct 25 at 23:59 ET, Demo Day Oct 29. Today is Wed Oct 21. Realistically there are about 2.5 build days for the app.
- **Phase 1 first:** the read-back (today), training (Thu) and the results report (Thu) stay on schedule.
- **Model limits** (from the reference docs):
  - at most about 15 options per decision
  - short inputs only (Laya's window is 512 tokens for the root checkpoint, still being verified)
  - Jev is weak at numbers, dates and multi-step rules
- **Keys** live in env vars only (`TYPESAFE_API_KEY`, `ANTHROPIC_API_KEY`, the Clerk keys, Modal auth). Nothing confidential goes in the repo.
- **Anthropic API use:** the in-app agent needs it. Phase 1 still rules out API-generated *training data* for the benchmark, but the product's agent and its live example generation do use the API.
- **TypeSafe's terms** ([Master Customer Agreement](https://typesafe.ai/legal/mca), read Oct 21). This is our reading, not legal advice:
  - **§2.2:** we may build Jev into an application we operate for our own users.
  - **§2.3(a):** we may not offer Jev as a standalone service.
  - **§2.3(b):** we may not use Jev or its output to develop a similar or competing product, distil it, or train a model to imitate it.
- **Hackathon rules:** we build during Build Week, and disclose prior work, templates and AI tools (including Claude Code).

## Product shape: two lanes on one road

Every project starts the same way and can stop early:

| Lane | What the user gets | Time | Needs training? |
|---|---|---|---|
| **Quick** (one-offs, small tasks) | Rules written with the agent, then a working endpoint and playground on **Jev with their rules attached** | Minutes | No |
| **Full** (larger tasks) | Everything in Quick, plus labelled examples, a trained sys1, an honest comparison, and a model that improves from corrections | Hours (training runs in the background) | Yes |

**Jev inside system1 (recommended, within the limits TypeSafe's terms set).** Jev with the user's rules is the default starting model in the Quick lane. Reasons:

- **It solves the cold start.** A user has value on day one, with no examples and no training.
- **It feeds the flywheel the right way.** Every decision is logged. When a person corrects one, that correction becomes a labelled example for their sys1.
- **We add real value on top of Jev.** We store the rules and attach them to every call, so the user sends only the ticket. We also give them a decision log, a feedback button, and a test set to measure against.
- **It's an honest fallback.** If sys1 doesn't beat Jev on someone's task, they still have a working endpoint, and the report card says so.
- **It enables `auto`.** sys1 answers when it's confident, and Jev with the rules answers when it isn't. Swapping between them is just a change to the `model` field.

**What TypeSafe's terms change** (see Constraints):

- **No training on Jev's answers, ever.** Training labels come only from:
  - the user's rules
  - the user's own past decisions
  - corrections a person makes

  Jev's answers are logged for display and comparison, and flagged as not for training. The Improve inbox picks items by sys1's own uncertainty, never by comparing with Jev, and never shows Jev's answer as a suggested label.
- **Not a Jev reseller.** The Jev lane is a feature inside system1 (rules attached, logging, review), not raw Jev access. In production each customer connects their own TypeSafe account, using their own key. For the hackathon demo we use our own key, which counts as us using Jev in our own application.
- **No claim of a relationship with TypeSafe,** on Devpost or in the video.
- **"Competing product" (§2.3b) is the open exposure.** sys1 is pitched as an alternative to Jev. For a hackathon prototype the practical risk is low. Before anything commercial, get TypeSafe's written OK. A short email to TypeSafe now costs nothing.
- **If TypeSafe says no,** the Quick lane can run on Claude with the user's rules instead of Jev.

## Design principles

1. **Never a blank page.** Every step opens with a draft the agent already made. The user reacts instead of writing from scratch.
2. **Buttons first, typing optional.** Every agent question comes with 2–4 clickable answers, plus a text box.
3. **Show the thing, not just the chat.** The rules, examples and results live on a canvas the user can see and edit directly. The chat is a guide, not the only way in.
4. **Plain words.** The UI says "options", "examples", "your model" and "how often it's right". Probabilities, splits and calibration go in a "Details" drawer.
5. **A working endpoint early.** The Quick lane ends with an API key before any training happens.
6. **Honest verdicts.** The report card says when Jev is better and why.
7. **Spending takes a click.** Example generation and training show time and cost estimates and wait for confirmation.

## Recommended journey: Guided build

The workspace has a stage rail across the top: **1 Use case · 2 Rules · 3 Try · 4 Examples · 5 Train · 6 Use · 7 Improve**. The agent sits on the left and the canvas for the current stage sits on the right. Users can jump back to any stage. Users sign in with Clerk before their first project is saved.

### 1. Use case

- **Screen:** a gallery of about 10 use cases (see "Use-case gallery"), a "Describe your own" box, and a "Help me find one" button.
- **Agent:** asks what team they're on, which decisions they make over and over, roughly how often, and what goes wrong today. It proposes three candidates, each with a fit rating (Good fit / Workable / Poor fit) and one-line reasons.
- **Clickables:** candidate cards, "Pick this", "Show me more like this".
- **Produces:** a project with a name, the decision question and a draft list of options.

### 2. Rules

- **Canvas, three panels:**
  - **Inputs:** the facts the decision depends on, like amount, days since purchase or plan.
  - **Options:** one card per outcome, each with "covers", "doesn't cover" and an example.
  - **Rules:** an ordered list, checked top to bottom, with the first match winning. Each rule has plain text. A rule that can also be checked by machine (for example `amount > 500`) gets a **testable** badge. One that needs judgment (for example "the customer sounds upset") gets a **needs judgment** badge.
- **Agent:** interviews one question at a time, with chips. It looks for the gaps that break real policies:
  - **Overlaps:** "A refund over $500 that also mentions fraud. Which wins?"
  - **Missing facts:** "What if the customer doesn't say the amount?" It suggests Tallyfern's "unknown means no" pattern.
  - **Leftovers:** it offers an "other" option.
  - **Too many options:** it suggests merging when the list passes about 15.
- **Clickables:** answer chips, "Add option", drag to reorder rules, "Looks right".
- **Produces:** policy v1, as readable text plus structured options and rules.

### 3. Try (the Quick lane ends here)

- **Screen:** a playground. The user pastes an input, or clicks "Give me 5 tricky examples" and the agent writes edge cases. The answer comes from **Jev with your rules**, with "Jev without your rules" next to it for contrast.
- **Each answer shows:** the chosen option, a probability bar, and ✓ / ✗ buttons. ✗ asks for the right option, and if the rules caused the miss, the agent proposes a rule edit.
- **Exit:** a **"Use it now"** button gives an API key and a code snippet for the Jev lane. The Quick lane is done, and the project can carry on to the Full lane at any time.

### 4. Examples

- **Source picker:**
  - **Generate from my rules** (default)
  - **Upload past decisions** (CSV, Could tier)
  - **Both**
- **Generate:** this is the phase 1 pipeline, automated:
  1. Sample the facts for each example, spread across options and pushed toward the edges near each threshold.
  2. Label each example by running the rules.
  3. Have Claude write the input text, which never names the answer.
  4. Run a blind read-back check.
  5. Split the examples into train, calibration and test sets.
- **Health panel:**
  - examples per option
  - the easy / borderline / tricky mix
  - the read-back pass rate
  - split sizes, with a lock icon on the test set
- **Spot-check:** 20 random examples, each with agree / disagree. A disagreement points at a rule or a writing problem.
- **Label-source badge:**
  - **"Labelled by your rules":** every rule is testable, which is the phase 1 method.
  - **"Labelled by Claude, checked by you":** some rules need judgment. The user is told this is less reliable.

### 5. Train

- **Start:** one button opens a confirmation card with an estimated time, an estimated cost and what happens next. Training runs as a Modal job, with plain progress stages: preparing, learning, checking, testing.
- **Report card:** sys1 against Jev with your rules, Jev with options only, and the untrained base model, all on test examples nobody trained on. It shows:
  - how often each is right, with an interval
  - per-option results
  - the main mix-ups, for example "confuses finance_review and billing_refunds near $500"
  - typical response time
  - cost per 1,000 decisions
- **Verdict and next step:** "Switch to your model", "Use auto", or "Stay on Jev and add examples", each with a one-line reason.

### 6. Use

- **Access:** the endpoint URL, an API key, and copy-paste snippets (curl, Python, JavaScript).
- **Model picker:** Jev with your rules, your model, or auto.
- **Later:** a CSV batch upload (Could tier) and an MCP config snippet (Future).

### 7. Improve

- **Inbox:** decisions sys1 was unsure about, and decisions a user flagged. Each has one-click correction. The inbox never uses Jev's answers to pick items or suggest labels.
- **Retrain:** a counter ("23 new answers since your last training") and a Retrain button. Every version is tested on the same frozen test set, and a small chart shows accuracy by version.
- **Rule changes:** when the user edits a rule, the agent offers to regenerate the examples that rule affects.

## Other journeys we considered

| Journey | How it goes | Strength | Weakness | Verdict |
|---|---|---|---|---|
| **A. Guided build** (above) | Gallery, then agent and canvas, then Jev endpoint, then examples, train, use, improve | Covers the whole story. Great for a demo and for non-technical users | The most to build | **Core product** |
| **B. Start on Jev, graduate later** | Write the rules, go live on Jev today, and corrections pile up. We train sys1 in the background and suggest switching when it wins on their test set | The best long-term business. Value before any training | The payoff takes time, so it's hard to show in a short video | **The pitch's "after onboarding" story.** The gateway and log make it real |
| **C. Bring your history** | Upload past decisions as CSV. The agent drafts rules from the data and flags inconsistent past labels, then training goes straight from there | Most realistic for real companies | Needs a realistic dataset (no real customer data allowed). Inferring rules is hard | Could tier, demoed with a synthetic CSV |
| **D. One-off batch** | No account. Upload a spreadsheet, describe the decision in a sentence, and get a labelled column back, from Jev with the rules | The lowest-friction hook for busy or non-technical users | No learning, so it's a commodity on its own | **Front door hook.** Could tier, but cheap once the Jev lane exists |
| **E. Start from your Claude** | The user asks their own Claude, which already knows how they work, to find decisions worth automating. Claude calls system1's MCP tools and creates a pre-filled project | Better brainstorming than a cold questionnaire, plus a strong privacy story | Needs a public MCP endpoint and OAuth. Invisible in a video | **Future** (see Roadmap) |
| **F. Chat only** | Everything happens in conversation, with no canvas | Simplest UI | Hard to scan or edit. Thomas asked for clickable flows | Rejected |
| **G. Form wizard, no agent** | A classic step-by-step form | Predictable | Loses the coaching and brainstorming | Rejected as primary. The editable canvas already works without the agent, so this is the fallback if the agent misbehaves |

**Recommendation:** build A, use D as the front door when there's time, and tell B as the story of what happens after onboarding.

## Screen designs

Wireframes for the four screens that carry the demo. Numbers shown as `xx` are placeholders, not results.

**Workspace (stage 2, Rules)**

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ system1   Acme Refunds ▾      ① Use case  ❷ Rules  ③ Try  ④ Examples  ⑤ Train  ⑥ Use  ⑦ Improve │
├────────────────────────────────┬─────────────────────────────────────────────────┤
│ Agent                          │ Inputs   amount · days since purchase · plan · reason │
│                                │                                                  │
│ A refund over $500 from an     │ Options (4)                              + Add   │
│ Enterprise customer. Should    │ ┌ approve ────────────────┐ ┌ escalate ─────────┐│
│ it still go to a manager?      │ │ covers: ≤ $500, ≤ 30 days│ │ covers: > $500 ...││
│                                │ └─────────────────────────┘ └───────────────────┘│
│ [Yes, always]  [No, approve]   │ ┌ deny ... ┐ ┌ fraud_review ... ┐                │
│ [Only if over $2,000]          │                                                  │
│                                │ Rules, checked in order, first match wins        │
│                                │ 1 ⋮ Signs of fraud anywhere → fraud_review   testable │
│                                │ 2 ⋮ Amount over $500 → escalate              testable │
│ ────────────────────────────── │ 3 ⋮ Customer sounds abusive → deny     needs judgment │
│ > Type a message               │                                    [Looks right] │
└────────────────────────────────┴─────────────────────────────────────────────────┘
```

**Playground (Tallyfern, trained)**

```
┌ Try a ticket ─────────────────────────────────────────── [Sample from test set ▾] ┐
│ "Hi, we were charged $640 for the annual upgrade last week and want it refunded." │
├──────────────────────────────────────────────────────────────────────────────────┤
│                        Answer              How sure      Time                     │
│ Jev, options only      billing_refunds     ████░░ xx%    xx ms                    │
│ Jev + your rules       billing_refunds     ███░░░ xx%    xx ms                    │
│ Your model (sys1)      finance_review  ✓   █████▉ xx%    xx ms                    │
│ Correct by your rules: finance_review  (R04: refund over $500)                    │
│                                                    [✓ Right]  [✗ Wrong → pick one] │
└──────────────────────────────────────────────────────────────────────────────────┘
```

Showing the correct answer and the rule behind it is the demo's clearest moment. Corrections on test-set tickets are stored as feedback but never used for training.

**Report card (stage 5)**

```
Your model vs Jev, on xx test tickets no model trained on

                      Right            Typical time   Cost per 1k
Your model (sys1)     ██████████ xx%   xx ms          $x.xx
Jev + your rules      ████████   xx%   xx ms          $x.xx
Jev, options only     ██████     xx%   xx ms          $x.xx
Untrained base        ███        xx%   xx ms          —

Verdict: your model is right xx points more often (95% range x to y).
Biggest mix-up: finance_review vs billing_refunds near the $500 line.
[Switch my endpoint to my model]  [Use auto]  [Details ▸]
```

**Use (stage 6)**

```
Endpoint   https://<app>/v1/systemone          Key  sk_sys1_••••••  [Copy] [New key]
Model      ( ) Jev + your rules   (•) Your model   ( ) Auto
┌ curl ─ Python ─ JavaScript ─────────────────────────────────────────────────────┐
│ curl https://<app>/v1/systemone -H "Authorization: Bearer $SYS1_KEY" \          │
│   -d '{"model": "sys1", "state": "Hi, we were charged $640..."}'                │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## The onboarding agent (website)

- **Job:** guide stages 1–4 and explain stages 5–7. It edits the canvas through tools, so the user always sees the result as structured options and rules, not just text in the chat.
- **Model:** `claude-opus-5-5` via the Anthropic Messages API, with tool use, the Python SDK's tool runner and streaming to the browser. Managed Agents and the Agent SDK aren't needed, because the agent has no files or shell, only our tools. Cost: Opus 5.5 is $4 / $20 per 1M input / output tokens. A full onboarding conversation should cost under about $1 (estimate, to be measured).
- **Tools:**

  | Tool | Effect | Needs a user click? |
  |---|---|---|
  | `show_choices(question, options)` | Renders answer chips | No |
  | `search_use_cases(query)` | Searches the gallery | No |
  | `fit_check(description)` | Returns a fit rating with reasons, against the fit criteria below | No |
  | `set_inputs`, `set_options`, `set_rules` | Updates the canvas, with a visible diff and undo | No |
  | `try_decision(input)` | Calls Jev with the current rules (and sys1 if it exists) | No |
  | `write_examples(n, kind)` | Writes a few sample or tricky inputs for the playground | No |
  | `generate_dataset(n, mix)` | Starts the example pipeline (costs money) | **Yes**, through a confirmation card |
  | `start_training()` | Starts a Modal job (costs money) | **Yes**, through a confirmation card |

- **State:** the canvas (policy JSON) is the source of truth. The agent gets the current canvas every turn, so the user's direct edits are never lost.
- **Memory:** for V1, the agent's memory is the project itself (the canvas plus the chat history). Remembering a user across projects is V3 (SurrealDB Agent Memory).
- **Guardrails:**
  - It never runs code it wrote on our server. Rules are data, not code (see below).
  - It treats pasted user content as data, not instructions.
  - It declines high-stakes decisions about people (hiring, credit, medical) without human review, and suggests a review step instead.

## The Claude Skill (`system1-onboard`)

- **What:** a Claude Code skill in `.claude/skills/system1-onboard/` (committed, unlike `agent-prompts/`). It walks a company through stages 1–4 in a Claude Code session and ends with a dataset ready for `make train`.
- **One playbook, two surfaces.** The skill's step-by-step instructions are also the base of the website agent's system prompt. The website maps each step to a tool. Improving the playbook improves both.
- **v1 for the hackathon:**
  - The stages: use case and fit check, rules interview, quick Jev check, facts schema, example writing, read-back, and building the dataset.
  - Tallyfern as the worked example, pointing at `data/policy/`, `policy.py`, `facts_grid.py`, `tickets.py`, `readback.py` and `build_dataset.py`.
  - In Claude Code, the examples are written in-session, as in phase 1, so no API spend.
  - Claude adapts our scripts per project.
- **v2 (Should tier):** the skill uses the same generic rules engine and sampler as the website.

## Rules as data

Each rule is stored as:

```json
{"id": "R02", "text": "Refund over $500 → escalate", "label": "escalate",
 "when": {"all": [{"field": "request", "op": "eq", "value": "refund"},
                  {"field": "amount_usd", "op": "gt", "value": 500}]}}
```

- `text` is always present and is what Jev sees in the policy prompt. `when` is optional. When every rule has a `when`, the project can label generated examples automatically. That's phase 1's "labels from rules, not judgment" method.
- One small engine evaluates `when`:
  - operators `all`, `any`, `not`, and `eq` / `ne` / `gt` / `gte` / `lt` / `lte` / `in` / `is_null`
  - the first matching rule wins
  - unknown means no

  No model-written code runs on the server.
- **Acceptance check:** port Tallyfern's `policy.route` to this format. Its 550 facts must produce the same labels. If the format can't express Tallyfern, it isn't good enough.

## AI engineering

**Lifecycle**

```
BUILD TIME (once per project)
rules ─► sample facts ─► rules engine ─► gold label (and the rule ID that fired) ──────────┐
              └────────► Claude writes text ─► leak check ─► blind read-back ─► facts match? ┴─► dataset
dataset ─► split once (train / calibration / test, test locked)
train LoRA (Unsloth, Modal L4, 3 seeds) ─► fit temperature on calibration ─► test against Jev and base
        ─► registry: candidate vN + metrics ─► goes live only if it beats the live version on the same test

RUN TIME
app ─► gateway ─► sys1 (Laya + adapter vN) ─► top probability ≥ τ ? ─ yes ─► sys1 answers
                                                                    └ no ─► Jev with rules answers, input goes to the inbox
       every call is logged with its input, answer, probabilities, policy version, model version, latency and cost
person ─► correction ─► (not a test item) ─► training pool ─► retrain ─► registry check
```

**Which model does what**

| Job | Model | Why |
|---|---|---|
| Gold labels | Rules engine (deterministic) | Correct by construction, and auditable |
| Writing examples, read-back check, onboarding agent | Claude Opus 5.5 | Writing quality and tool use |
| Answers with no training, and the baseline | Jev 1.13.0 | Works immediately. Never used as a teacher |
| The team's own model | Laya + LoRA | One forward pass (published p50 ≈ 33 ms), and trainable |

**Design decisions that matter most**

1. **One question builder for training, testing and serving.** The same function renders what sys1 sees at every stage. If training and serving format inputs differently, a fine-tuned model quietly does worse in production, so we rule that out. Option order is shuffled and recorded, because Jev favours whichever option comes first.
2. **The input limit is enforced at the edge.** The gateway measures every input against Laya's window, and the example generator caps length, so live inputs look like training inputs.
3. **Calibrate, then route.** We fit a temperature on the calibration split. The `auto` threshold τ is chosen there to hit a target accuracy on the answers sys1 keeps (for example 97%), and then reported on test. Everything uses probabilities, not `confidence`.
4. **A model registry with a check before going live.** Every retrain produces a candidate. It replaces the live version only if it beats it on the same frozen test set (paired bootstrap). Noisy corrections can't silently make things worse.
5. **Old examples mixed into every retrain.** New human corrections train alongside the original rule-labelled set, so the model learns from real traffic without forgetting the rules.
6. **Lineage on every decision.** Each logged decision records the policy, dataset and model versions. Any answer can be traced, and any regression traced back to the version that caused it.
7. **Many customers share one GPU.** One base Laya model stays in GPU memory, adapters are loaded per project and cached, and requests are batched. That's what makes a model per customer affordable.
8. **Drift signals.** We watch three things:
   - the share of `auto` traffic that falls back to Jev
   - the average top probability
   - the mix of corrections

   A rising fallback rate means inputs are drifting away from the training data, which is the signal to regenerate examples or retrain.
9. **Answers that cite the rule (S5, to test).** sys1 is trained on a second question, "which rule applies?", with the gold rule ID from the rules engine. Laya answers several questions per input, so the model can say "finance_review, because R04: refund over $500". Jev can't be trained against a team's rule IDs. The cost is that the second question uses part of the 512-token budget. Nicholas runs a quick test, and we keep it only if queue accuracy holds.

## Security and ethics

- **Prompt injection has nowhere to go.** sys1 and Jev can only pick one of the project's options, so instructions hidden in a ticket can't make them act. Only the onboarding agent writes free text, and its money-spending tools wait for a click.
- **Accounts and access:**
  - Clerk handles sign-in.
  - API keys are scoped to one project and stored hashed.
  - Every query is filtered by project, so one customer can't read another's data.
- **Data handling:** inputs are stored for the decision log under a retention setting. Nothing confidential goes in the repo, and the demo uses synthetic data only.
- **People stay in the loop:**
  - unsure decisions go to a person
  - high-stakes decisions about people are declined
  - every decision is in an audit log with its model and policy versions
- **Training data rules:** no training on Jev output, and no test-set items in training. See "What TypeSafe's terms change".
- **Spending limits:** caps per session on the Anthropic API, and confirmation cards before generation and training.

## Use-case gallery and fit check

**Fit criteria** (the agent's `fit_check` and the gallery badges):

- The same decision is made often: hundreds of times a month or more.
- There's a fixed list of 2–15 outcomes.
- The input is short: a message or a few fields, a few paragraphs at most.
- The rules can be written down, or past decisions exist.
- A wrong answer can be caught: there's a human review step or it's cheap to undo.
- **Bonus, where sys1 should shine:** rules with numeric thresholds, time windows or precedence. These are Jev's documented weak spots, and fine-tuning teaches the specific thresholds.
- **Poor fit:** long documents, open-ended writing, decisions that need a live lookup not in the input, and high-stakes decisions about people without review.

**Starting gallery** (static JSON. Each entry has the decision, the options, the inputs, a sample input and 2–3 sample rules):

| Use case | Options (examples) | Status |
|---|---|---|
| Support ticket triage (Tallyfern) | 13 queues | **Trained, flagship demo** (the flagship is configurable) |
| Refund approval | approve, escalate, deny, fraud review | Template. The live demo's new project |
| Inbound lead routing | rep teams by region or size, nurture, disqualify | Template |
| Shared-inbox email routing | sales, support, billing, partnerships, spam | Template |
| Expense report check | approve, needs receipt, policy violation, escalate | Template |
| Community content moderation | allow, warn, remove, review | Template |
| Bug report triage | component, severity | Template |
| Order exception handling | reship, refund, contact carrier, fraud review | Template |
| Transaction categorization | bookkeeping categories (≤15) | Template |
| IT helpdesk routing | hardware, access, software, security | Template |

## Gateway API (Jev-compatible)

```
POST /v1/systemone
Authorization: Bearer <project key>
{
  "model": "auto",                 // "jev-1.13.0" | "sys1" | "sys1@v3" | "auto"
  "state": "<input text or object>",
  "questions": { ... }             // optional; omitted → the project's saved question
}
→ Jev's response shape, plus:
  "system1": {"decision_id": "...", "routed_to": "sys1@v3", "policy_version": 2, "latency_ms": 41}

POST /v1/feedback  {"decision_id": "...", "correct": {"queue": "finance_review"}}
```

- **Jev lane:**
  - Builds the "Jev with policy" question from the project's rules, using the same builder as the benchmark row, so the two can't drift.
  - Calls TypeSafe pinned to `jev-1.13.0` and logs the `model` field from each response.
  - Uses the customer's own TypeSafe key in production.
  - Stores Jev answers with a `not_for_training` flag.
- **sys1 lane:** sends the question in the format sys1 was trained on to the Laya server.
- **auto:** sys1 answers when its top probability clears a threshold fitted on the calibration split, using probabilities, not `confidence`. Otherwise Jev with rules answers, and the input also lands in the Improve inbox so a person can label it.
- **Logging:** every call is logged with its input, answer, probabilities, model, latency and cost.

## Architecture

```
Client: React (Vite, TypeScript, Tailwind) with Clerk sign-in, in the browser
   │ REST + server-sent events (agent stream)
Server: FastAPI (one Modal app, web endpoint; verifies Clerk sessions)
   ├─ Agent ─────────── Anthropic API (claude-opus-5-5)
   ├─ Pipeline ──────── rules engine · facts sampler · example writer + read-back (Anthropic API) · dataset builder
   ├─ Jobs ──────────── Modal functions: train (L4), eval
   ├─ Registry ──────── model versions (candidate / live) with metrics and lineage
   ├─ Gateway /v1/systemone ─┬─ TypeSafe Jev (jev-1.13.0)
   │                         └─ Laya server (Modal GPU class: base Laya + one LoRA per project)
   └─ SQLite + parquet files on a Modal Volume
```

- **Hosting:** one Modal app serves the API and the built React files, so there's one URL. The Laya server is a separate GPU class in the same app, kept warm during judging.
- **Serving many models:** one base Laya with a small adapter per project, so customer models share a GPU. That's also the business story on cost.
- **Data (SQLite tables):**
  - `users` (the Clerk user id)
  - `projects` (with the owner)
  - `policies` (versioned: inputs, options, rules, text)
  - `datasets` (version, split sizes, label source)
  - `models` (version, status `candidate` or `live`, adapter path, metrics, dataset version)
  - `decisions` (the gateway log, with policy and model versions)
  - `feedback`
  - `api_keys` (hashed)
  - `agent_messages`
- **Sign-in:** Clerk on both the client and the server. API calls to the gateway use project keys instead.
- **Repo layout:** `app/server/`, `app/client/` and `.claude/skills/system1-onboard/`. We always say "client" and "server", never "frontend" and "backend". The phase 1 scripts stay where they are. Coordinate with Nicholas before touching `train.py`.

## Contracts and modularity

Nicholas may not be reachable this week, and the training approach will probably change as we learn. So the product talks to the model side only through four small contracts, each with a fake for development and tests. Changing how sys1 is trained or served means writing or swapping one adapter, not touching the app.

| Contract | Shape | Where it comes from today | Fake in V1 |
|---|---|---|---|
| **Dataset rows** | `id`, `split`, `state`, `questions` (Jev's request shape) and `gold`, plus metadata (difficulty, rule ID, option order) | Phase 1's parquet, written by `build_dataset.py` | The Tallyfern provisional parquet |
| **Decision provider** | `decide(state, questions, model)` returns answers with probabilities, the model version, latency and usage | Jev's request and response shape, which `laya-serve` and Unsloth Studio also speak | A deterministic fake provider |
| **Trainer** | `start(dataset, config)` returns a job id. `status(job_id)` and `result(job_id)` return an adapter reference and metrics | `train.py` on Modal. This is Nicholas's code: we wrap it and don't edit it without him | A fake trainer that finishes with fixed metrics |
| **Evaluation results** | Per-answer records `{id, question, pred, gold, confidence, p_gold, correct}` plus a summary file | The output `eval_common.py` writes to `results/` | Fixture files |

- **Ports and adapters.** The core (projects, rules engine, routing, registry, decision log) imports no vendor SDK. Adapters for Anthropic, TypeSafe, the sys1 server, Modal, Clerk and storage sit at the edge, and configuration picks which one runs. Every adapter has a fake.
- **sys1 by URL.** The default sys1 adapter calls any Jev-compatible endpoint, set by a base URL and a model id. If Nicholas's server ends up with a different shape, we add one adapter class that maps it.
- **If Nicholas can't serve sys1 in time,** Block C serves it with `laya-serve` or Unsloth Studio on Modal, behind the same adapter. It reuses the adapter-loading code in `eval_lora.py`. `train.py` stays untouched unless Nicholas agrees.
- **Engineering basics:**
  - typed models at every boundary: Pydantic on the server, and TypeScript types for the client generated from the server's OpenAPI schema
  - small modules with one job each
  - configuration from environment variables
  - linting and formatting
  - unit tests on the core, plus contract tests that run each adapter and its fake against the same cases
  - one end-to-end click-through
- **Design changes are expected.** When the training approach changes, the contracts absorb it. If a change has to cross a contract, update the contract and its tests first.

## Roadmap

| Version | What | When |
|---|---|---|
| **V1: hackathon product** | Everything in the Must and Should tiers below, including Clerk sign-in | By Oct 25 |
| **V2: Era by Eon** | Test and benchmark the onboarding agent with Era. Scripted user conversations check that it asks about overlaps, catches missing facts, and never starts a paid step without a click. Qualifies for the Eon prize | After V1 is built. Before submission if there's time, otherwise after |
| **V3: SurrealDB Agent Memory** | The agent remembers a user's workflows, past projects and preferences across sessions, so the second project starts from what it already knows. Qualifies for the SurrealDB prize | After V2, if there's time |
| **Future** | See below | After the hackathon |

The full running list, including maybe items and things to check, is in [docs/backlog.md](../../backlog.md).

**Future:**
- **The Claude connector and MCP server (journey E).**
  - system1 tools (`suggest_use_cases`, `fit_check`, `create_project`, `try_decision`, `decide`, `feedback`) callable from Claude.
  - A user's own Claude, which already knows how they work, brainstorms with them and creates pre-filled projects. The first step is a "Brainstorm with your Claude" button that copies a prompt and accepts the pasted answer. After that comes a local MCP server for Claude Code and Claude Desktop, then a remote connector for claude.ai with OAuth.
  - A third-party app can't query a user's Claude directly, so the integration has to run in this direction.
- Team accounts and roles (Clerk organizations), and billing.
- Customers' own TypeSafe keys, and any TypeSafe partnership.

## Hackathon cut

| Tier | Piece | Owner |
|---|---|---|
| **Must** | M1 Gateway: Jev lane with rules attached, sys1 lane for the flagship project, decision log, project keys | Thomas |
| | M2 sys1 served on Modal behind the Jev-compatible shape | Nicholas, or Thomas with `laya-serve` or Unsloth Studio if Nicholas isn't free |
| | M3 Flagship playground and report card, built from phase 1's results | Thomas |
| | M4 Gallery, workspace and agent for stages 1–3 (use case, rules, try on Jev) | Thomas |
| | M5 Use page: key, model picker, snippets | Thomas |
| | M6 Feedback ✓ / ✗ stored and listed in the Improve inbox | Thomas |
| | M7 `system1-onboard` skill v1 | Thomas |
| | M8 Deployed at a public URL and warm during judging | Both |
| | M9 Clerk sign-in, with projects owned by users | Thomas |
| **Should** | S1 Examples stage live for a new project: 20–50 examples, labelled by rules, read-back, spot-check | Thomas |
| | S2 `auto` routing with the calibrated threshold | Nicholas |
| | S3 Retrain from corrections, with the registry check (only if phase 2 passes its gate) | Nicholas |
| | S4 Generic rules engine shared by the skill and the site, with the Tallyfern port as its test | Thomas |
| | S5 Answers that cite the rule (rule-ID question), if queue accuracy holds | Nicholas |
| **Could** | C1 Train a new project's sys1 from the UI · C3 One-off CSV batch (journey D) · C4 Bring-your-history CSV (journey C) | Whoever is free |

Era by Eon, SurrealDB Agent Memory and the MCP server live in the Roadmap, not in this table. The maybe items (ideas to revisit but not planned) and every future idea are tracked in the running catalog, [docs/backlog.md](../../backlog.md).

If phase 1 slips, the Must list shrinks to M1, M2, M3, M5, M8 and M9: the benchmark story with a live endpoint and sign-in.

**What's live in the demo and what isn't.**
- **Live:**
  - the gallery
  - the agent writing rules for a new project
  - Jev with those rules in the playground
  - the flagship sys1 against Jev on any ticket
  - the curl call
  - feedback
- **Not live:** the flagship model's training, which ran Thursday. We show the real run's date, duration and results, and say so.

Any step that isn't live is labelled as such in the video.

## Build approach: blocks and gates

Claude builds in blocks on the `product-design` branch, in the main checkout (no separate worktree). Phase 1 data work happens in the same checkout, so its outputs get committed separately from app code, which keeps them easy to bring into `main` on their own. Every task has an automated check. Thomas comes in only at gates, where a person has to decide something or an account is needed. Each gate takes about 10–20 minutes and comes with a short report and screenshots. This is the high-level plan. The detailed implementation plan gets written with Thomas in a separate session before Block A starts.

| Gate | When | What Thomas does | Time |
|---|---|---|---|
| **G0 Kickoff** | Wed Oct 21, evening | Approve this spec. Add the Anthropic and Clerk keys to `.env`. Confirm Modal sign-in works | 20 min |
| **G1 Plan** | Thu Oct 22, morning | Write and approve the implementation plan with Claude. The plan pins down the four contracts (see "Contracts and modularity"), and Nicholas reviews them when he's available | 30–40 min |
| Block A (automatic) | Thu | Scaffold, store, Clerk sign-in, gateway Jev lane, gallery, playground on Jev | none |
| **G2 Click-through** | Thu evening | Click through the app locally and fix wording | 15 min |
| Block B (automatic) | Thu–Fri | Agent stages 1–3, confirmation cards, Use page, feedback and inbox, skill v1 | none |
| **G3 Agent check** | Fri midday | One real onboarding conversation. Note anything that feels off | 15 min |
| **G4 Decision gate** | Fri | Phase 1 results are in, so pick the demo story. The real sys1 server is plugged in behind the provider adapter, whoever ends up serving it | 20 min |
| Block C (automatic) | Fri–Sat | Real report card, sys1 and `auto` lanes, deploy to Modal, Should-tier items, then V2 if there's time | none |
| **G5 Rehearse** | Sat Oct 24 | Run the demo on the live URL. Record the video | 1–2 h |
| **G6 Submit** | Sun Oct 25 | Review the Devpost write-up Claude drafted, then submit | 30 min |

**What lets it run without Thomas:**
- **Stand-ins for every outside service** (Claude, Jev, Modal, sys1, Clerk), so tests are free and deterministic. Real calls happen only in one tagged smoke test with a spending cap.
- **One `make verify`.** It runs the unit tests, the client build, an automated browser click-through and screenshots. A block isn't done until it passes, and its output is the gate report.
- **A fake sys1 provider** that speaks the decision-provider contract, so the app never waits on the real server. Swapping in the real one is a configuration change, or one adapter class if its shape differs.
- **A progress note at the end of each block** in the progress ledger, so Thomas can catch up in two minutes.

**Commits:** Claude commits freely on the product branch with plain messages and no Claude attribution lines. Claude never commits to `main`. Thomas merges after reviewing at a gate.

**Things only Thomas can do:**
- keys and account sign-ups (Clerk, and Era for V2)
- Modal deploy permissions
- the email to TypeSafe
- approving spend above the caps
- coordinating with Nicholas
- recording the video
- attending Demo Day if we make the top 10
- submitting on Devpost

## Demo video storyboard (about 3:00, limit 4:00)

| Time | Scene |
|---|---|
| 0:00–0:15 | The user and the problem: a team whose routing rules live in a doc. Jev is fast and cheap but doesn't know those rules, and misses the thresholds |
| 0:15–0:45 | Sign in, then pick "Refund approval" from the gallery. The agent asks three questions with chips, and the options and rules appear on the canvas |
| 0:45–1:00 | Try: Jev with your rules answers right away. "Use it now" gives a key. The Quick lane is done in about two minutes |
| 1:00–1:15 | Examples: 30 generated, labelled by the rules, spot-checked (S1, if built) |
| 1:15–1:45 | Switch to the flagship project: the report card (real numbers, from the labelled recorded run), then the playground on the $640 refund ticket, sys1 against Jev |
| 1:45–2:25 | How it works: the architecture, rule-labelled data, the frozen test set, answers that cite the rule (if S5 lands), and the guardrails |
| 2:25–2:45 | Use: a curl call, then a correction landing in the Improve inbox |
| 2:45–3:00 | "Start on Jev today. Graduate to a model that knows your rules." |

## Timeline and ownership

| Day | Thomas | Nicholas |
|---|---|---|
| Wed Oct 21 | Run the read-back and build the dataset (phase 1). G0 | Generalise `train.py` and chase the LoRA gap (phase 1) |
| Thu Oct 22 | G1. Jev benchmark runs and the results report (phase 1). Block A, then G2 | Train sys1 (seeds and the learning curve). Base Laya eval. Review the contracts when available |
| Fri Oct 23 | Decision gate (G4). Block B, then G3 | Serve sys1 on Modal. Gateway sys1 lane. S5 test |
| Sat Oct 24 | Block C. Deploy, rehearse and record (G5) | Phase 2 retrain if the gate passed. Keep the endpoint warm |
| Sun Oct 25 | Buffer. Devpost write-up (disclose earlier Modal and Unsloth experiments, templates, and AI tools used). Submit by 23:59 ET (G6) | Buffer |

Thomas decided to start the app on Thursday, before the decision gate, and to build it on the side with minimal hands-on time. He won't hear from Nicholas for now, so the build doesn't wait on him. Everything on Nicholas's side sits behind the contracts, with fakes until the real pieces arrive. The parts started early (gateway, Jev lane, agent, gallery) are useful whatever the benchmark shows.

## Business story (for Devpost and the pitch)

- **Who pays:** teams with thousands of repeated decisions a month, such as support, operations, finance and sales ops. The buyer is whoever owns the decision.
- **How it sells:** B2B, self-serve first. One person tries the Quick lane free, shows it works, and the team pays.
- **Pricing shape:**
  - a free playground and Quick lane on Jev, with a cap
  - per-decision pricing for hosted endpoints, with training included
  - paid "we build it with you" onboarding for larger tasks
- **Why it compounds:** every correction makes the customer's model better. Their rules and decision log become their asset, and switching away means losing that.
- **Honest cost and speed line:**
  - Jev is very cheap per call ($0.042 per 1M input tokens).
  - sys1's cost edge appears at volume, when many customers' adapters share GPUs, or when a customer self-hosts.
  - Speed: Laya's model card reports p50 ≈ 33 ms against about 250 ms for Jev. That's third-party and still to be measured on our setup.
- **Jev in production** runs on each customer's own TypeSafe account, or under a partnership if TypeSafe wants one.
- **If sys1 doesn't win the benchmark,** the product still works: the Jev lane, rules management, the log, feedback and the honest report card. The pitch shifts to speed, cost at volume, owning your model, and routing to whichever model wins on your test set.

## Risks

| Risk | Plan |
|---|---|
| App work starves phase 1 | Phase 1 tasks come first each day. Cut from the bottom of the tier list |
| The agent misbehaves in a live demo | The canvas works without the agent. Seed a demo project. Record the video from a rehearsed run |
| A cold GPU during judging | Keep the Laya server warm for the judging window. `auto` falls back to Jev |
| TypeSafe's terms (§2.3a standalone service, §2.3b competing product and training on output) | Keep the Jev lane inside our app: our key for the demo, customers' own keys in production. Never train on Jev answers. Email TypeSafe. Claude with the rules is the Quick-lane fallback |
| The rules format can't express real policies | The Tallyfern port is the acceptance test |
| Anthropic spend runs away | Per-session caps. Live generation in small batches only |
| Prompt injection through pasted inputs | Money-spending tools need a user click. No model-written code runs on the server |
| Clerk integration eats time | Use Clerk's prebuilt React components and server-side session verification. No custom auth UI |
| Scope creep (Era, SurrealDB, MCP, CSV) | Roadmap items wait until every Must is done. Could items wait until every Should is done |
| Nobody can attend Demo Day in Toronto | Confirm who goes before submitting |

## Answered questions (Oct 21)

1. **TypeSafe** is not a sponsor or a judge. Its terms are covered under Constraints and "What TypeSafe's terms change". The demo shows the Jev lane for real, using our own key inside our own app.
2. **Starting the app on Thursday:** yes. It's built on the side with minimal hands-on time.
3. **Anthropic API budget:** yes, `claude-opus-5-5` throughout. The rough estimates are about $5–10 per 500 generated and read-back-checked examples, and under about $1 per onboarding conversation.
4. **Nicholas owning sys1 serving (M2):** probably. The demo project may not end up being Tallyfern, so the flagship project is configuration, not code. M2 matters because serving is what makes "your model" real in the product. Without a live sys1 behind the endpoint, the playground's sys1 row, the `sys1` and `auto` lanes, and "Switch to your model" can only replay recorded results. The serving code is generic: base Laya plus whichever adapter the flagship project has.
5. **Market:** B2B, for any team with a repeated decision; support triage is the first use case.
6. **Category prizes:** Clerk in V1, Era by Eon in V2, SurrealDB Agent Memory in V3 if there's time.
7. **Commits:** Claude may commit on feature branches without asking, never on `main`, and never with Claude attribution.

## Decision log

**Decided by Thomas:**

- A website (FastAPI server, React client) as the main product, rather than MCP first.
- An onboarding agent in the website with plenty of clickable controls, plus a Claude Skill.
- A use-case library and agent-led brainstorming.
- Offering Jev access through system1, with setup help for both larger tasks and quick one-offs.
- Continuous learning from user feedback.
- TypeSafe is not a sponsor or judge. The demo shows the Jev lane live.
- Start the app on Thursday, built on the side with minimal hands-on time.
- `claude-opus-5-5` for the agent and example generation.
- The flagship demo project is configurable. Tallyfern is the likely choice.
- B2B, for any team with a repeated decision; support triage is the first use case.
- Clerk sign-in in V1. Era by Eon in V2. SurrealDB Agent Memory in V3 if there's time.
- The Claude connector and MCP server move to Future.
- Build in blocks with gates, with the detailed implementation plan written with Thomas first.
- Build now on the `product-design` branch, without waiting for Nicholas. Keep the code modular and clean, and keep the model side easy to plug in and to revise as training changes.

**Claude's calls**, open to change:

- Jev with your rules as the default starting lane, with sys1 as the upgrade. It lives inside system1, and customers use their own TypeSafe keys in production.
- Jev's answers are never used for training or for choosing what gets labelled.
- The two-lane structure (Quick and Full) and the seven stages.
- The agent on the left, the editable canvas on the right, and a stage rail.
- Journey A as the core, D as the front door and B as the pitch's "after" story. C is Could tier, E is Future, and F and G are rejected.
- `claude-opus-5-5` via the Messages API and tool runner, not Managed Agents or the Agent SDK.
- Rules as data, with optional machine conditions, and auto-labelling only when every rule is testable.
- One playbook shared by the skill and the website agent.
- A single Modal app and SQLite.
- The AI-engineering decisions: one question builder, the registry check before going live, mixing old examples into retrains, lineage, the rule-ID question (S5).
- The four contracts (dataset rows, decision provider, trainer, evaluation results), with ports and adapters, and a fake for every outside service.
- Refund approval as the live demo's new project.
- The Must / Should / Could tiers, the gates and the timeline.
- A video of about 3 minutes, with a section on how it works.
- Corrections on test-set items never train.

## Left to the builder

- The component library and styling. A clean, light UI is the default, and any template used must be disclosed.
- File layout inside `app/`.
- Server-sent events or websockets.
- Client state management.
- Exact tool schemas and prompt wording.
- Polling or callbacks for Modal jobs.
- The chart library.
- The SQLite access layer.
- The API key format.
