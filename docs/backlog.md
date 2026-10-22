# Backlog: maybes, future items and things to revisit

A running catalog of ideas we've parked. Nothing here is planned until it moves into a spec or plan.

- **Adding an item:** put new items in the right section, with the date.
- **When an item is picked up or dropped:** move it to "Done or dropped", with a line on what happened.

Last updated: Oct 21, 2026. The current plan lives in the [product design](superpowers/specs/2026-10-21-system1-product-design.md).

## Maybe (revisit later)

| Item | What it is | Why it's parked | Added |
|---|---|---|---|
| Label disagreement check | Opus labels each generated example from its text and the policy, without seeing the correct label. Wherever it disagrees with the rules engine, the example is flagged for a fix or a rewrite. Flagged examples are never silently dropped, because that would remove the hardest cases. On the test set, flag only and never filter, or the test leans toward examples LLMs find easy | Phase 1's pipeline is already running, and the read-back already checks facts | Oct 21 |
| Two-labeller consensus for judgment rules | For rules marked "needs judgment", two independent Claude passes label each example (two prompts, or Opus plus Sonnet). Agreements are accepted, and only disagreements go to the user | Only matters once projects have judgment rules (S1 or later) | Oct 21 |
| Jev disagreement view on the report card | Where Jev and sys1 disagree on the test set, show which one matched the rules | Evaluation only, which TypeSafe's terms allow. Good demo material if there's time | Oct 21 |

## Roadmap (planned after V1)

| Version | Item | Notes | Added |
|---|---|---|---|
| V2 | Era by Eon | Test and benchmark the onboarding agent with scripted conversations. Does it ask about overlaps, catch missing facts, and never start a paid step without a click? Qualifies for the Eon prize. Check what Era actually does first | Oct 21 |
| V3 | SurrealDB Agent Memory | The agent remembers a user's workflows, past projects and preferences across sessions. Qualifies for the SurrealDB prize. Only if there's time | Oct 21 |

## Future

| Item | What it is | Notes | Added |
|---|---|---|---|
| Claude connector and MCP server | The user's own Claude, which already knows how they work, brainstorms decisions worth automating and creates pre-filled projects through system1 tools: `suggest_use_cases`, `fit_check`, `create_project`, `try_decision`, `decide` and `feedback` | Steps: a copy-paste "Brainstorm with your Claude" button, then a local MCP server for Claude Code and Desktop, then a claude.ai connector with OAuth. A third-party app can't query a user's Claude, so the integration has to run in this direction | Oct 21 |
| Train a new project's model from the UI (C1) | A Train button that runs the whole pipeline for any project, not just the flagship | Could tier for V1 | Oct 21 |
| One-off CSV batch (C3, journey D) | No account needed: upload a spreadsheet, describe the decision, get a labelled column back | Could tier. The cheapest front door once the Jev lane exists | Oct 21 |
| Bring your history (C4, journey C) | Upload past decisions. The agent drafts rules from them and flags inconsistent past labels | Could tier. The demo would need a realistic synthetic CSV | Oct 21 |
| Team accounts and roles | Clerk organizations, so a team shares projects | After V1 | Oct 21 |
| Billing | Per-decision pricing for hosted endpoints, with training included | After V1 | Oct 21 |
| Customers' own TypeSafe keys | The production Jev lane runs on each customer's TypeSafe account | Needed before real customers (TypeSafe §2.3a) | Oct 21 |
| TypeSafe partnership | A formal arrangement, if TypeSafe wants one | Only matters if this becomes a real product | Oct 21 |
| Real trainer adapter | Connect training to the product through the `Trainer` contract, so "Train my model" and Retrain work from the UI | After the training approach settles | Oct 21 |
| Registry check before going live | A new model version replaces the live one only if it beats it on the same frozen test set (paired bootstrap) | Needs the real trainer adapter | Oct 21 |
| Drift signals | Track the share of `auto` traffic falling back to Jev and the average top probability over time | After real traffic exists | Oct 21 |
| API-generated data at scale | Thousands of examples per project through the Anthropic API | From phase 4 of the phase plan | Oct 20 |
| Qwen3.5-2B as the base model | The backup if Laya's input window or option budget becomes the bottleneck | From phase 4 of the phase plan | Oct 20 |
| Expansion use cases | Refunds, lead routing and expense checks for the same buyer | After the first customer | Oct 21 |

## To check or decide

| Item | Why it matters | Owner | Added |
|---|---|---|---|
| Nicholas reviews the four contracts | Dataset rows, decision provider, trainer and evaluation results are defined without him for now (product spec, "Contracts and modularity") | Nicholas | Oct 21 |
| Confirm the sys1 serving contract with Nicholas | The app assumes Jev's request and response shape, behind the decision-provider adapter. If his server differs, we add one adapter class | Thomas | Oct 21 |
| Laya's real input window (512 or 2,048) | Sets how long tickets and option descriptions can be | Nicholas | Oct 20 |
| Why our LoRA scores 0.658 against about 0.77 published | Needs explaining before we rely on the training pipeline | Nicholas | Oct 20 |
| The rule-ID question (S5) | Keep it only if queue accuracy holds | Nicholas | Oct 21 |
| Who attends Demo Day in Toronto (Oct 29) | At least one of us must be there in person if we make the top 10 | Both | Oct 21 |
| What Era by Eon actually does | Before committing to V2 | Thomas | Oct 21 |

## Decided against (kept for the record)

| Idea | Why not | Added |
|---|---|---|
| Jev labels the training data, with or without Opus reviewing | TypeSafe §2.3(b) forbids it, it caps sys1 at Jev's quality, and rule labels are free and correct | Oct 21 |
| A chat-only UI (journey F) | Hard to scan or edit, and we want clickable flows | Oct 21 |
| A form wizard as the main UI (journey G) | Loses the coaching. The editable canvas already covers it as the fallback | Oct 21 |
| Consumer or hobbyist focus | The pitch is B2B. Hobbyists get the free tier | Oct 21 |
| No sign-in for the demo | Reversed. Clerk is in V1, for security and the prize | Oct 21 |

## Done or dropped

| Item | What happened | Date |
|---|---|---|
| Email TypeSafe about the project | Dropped. Thomas confirmed that using Jev in the product and the demo is fine | Oct 21 |
