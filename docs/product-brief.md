# system1 product brief

As of 2026-10-25 · Thomas Michalski and Nicholas Stranges · Build North

## Summary

system1 turns a decision a team makes again and again into its own small decision model, trained on that team's examples and served behind the same API as Jev, TypeSafe's general decision model.

The bet: on a team's own decisions, a small fine-tuned model ("sys1", a LoRA on the 421M-parameter Laya model) is more accurate than Jev, at Jev's latency or better and lower cost. Switching costs one base URL, because the endpoint (`POST /v1/systemone`) speaks Jev's request and response format.

The headline test is BANKING77, 77 real customer-support intents with human labels. It is the benchmark where Laya's own model card shows Jev furthest ahead: 87.0% to 42.5% for untrained Laya.

## The problem

General decision models are good at everyone's decisions and so-so at any one team's. Jev cannot be fine-tuned on customer data: a team can only shape it through the question, the instructions and the bucket descriptions it sends.

That leaves three gaps a team feels every day:

- **Accuracy on their own buckets.** Fine distinctions that matter to one team (a transfer that is pending versus one the recipient never got) are exactly where a general model guesses.
- **Many options.** Jev's prompt budget is shared across options; above about 20, accuracy drops. Real routing schemes often have 30 to 80 buckets.
- **Honest confidence.** The Laya model card reports Jev's expected calibration error at 0.246, against Laya's 0.081, both after temperature scaling (its Jev numbers are third-party). An over-confident "how sure" cannot safely decide what a person should check.

The usual fix, fine-tuning, is out of reach for most teams: it needs labelled data, ML engineers and GPUs. system1 packages all three.

## Who it's for

Any team with a decision it makes again and again and wants a model to make for it. Support routing is one example: which queue, intent or team each incoming message goes to. Others are refund approvals, lead routing, expense and policy checks, and content or document classification. Today these decisions are made by a person reading each case, rules that break, or a general model the team can't tune.

The moment a team needs system1 is when those mistakes start to cost something they can see: work bouncing between queues, slow responses, people redoing decisions by hand. They have past decisions in an export somewhere, but no ML team.

What they get:

- a model that knows their buckets, including the ones that look alike
- a "how sure" signal they can act on: send sure answers straight through, send unsure ones to a person
- an endpoint their existing Jev integration can call without code changes

## What it does

The product is a guided journey with an onboarding agent (Claude) at each step. It runs as a loop: once a model is live, Use and Improve feed each other.

1. **Define.** Name the decision and its buckets. The agent drafts buckets and guidelines from pasted examples or uploaded documents.
2. **Data.** Upload past decisions (CSV, Excel or JSON) or generate practice examples. A data health panel shows which buckets need more. The test split is frozen at the first training.
3. **Review.** Check the examples the model is least sure about before training on them.
4. **Train.** Fine-tune on Modal. The report card scores your model, Jev and untrained Laya on the same frozen test examples, with confidence intervals, a verdict, speed, a learning curve, where your model beats Jev by bucket and what it mixes up.
5. **Use.** Try a message against your model and Jev side by side, create an API key and call the endpoint. Every trained model is kept, and an admin picks which one is live.
6. **Improve.** Check a batch of new messages, correct the answers the model wasn't sure about, and teach it again. The new version is compared with the live one on the same test set and recommended only if it scores higher. It goes live only when an admin clicks "Make live".

## Why it wins

**The pitch.** BANKING77 is Jev's best result against Laya. If a few minutes of fine-tuning on a team's own examples turns that into a win, the argument for per-team models makes itself, on public, human-labelled data anyone can check.

**First result.** Our first run through the product used 4,868 BANKING77 examples across all 77 intents (3,422 train, 459 calibration, 988 test) and three training epoch:

| Model | Test accuracy | Median latency |
| --- | --- | --- |
| Jev (`jev-1.13.0`) | 78.3% | 230 ms |
| sys1 | 80.4% | 78 ms |
| Untrained Laya | 33.4% | | |

Fine-tuning more than doubled Laya's accuracy and answers about 3 times faster than Jev, but this first run did not beat Jev. Two caveats cut in opposite directions:

- **sys1 was under-trained.** One epoch on about 44 examples per intent. The full BANKING77 train split has about 9,000 examples, and Unsloth recommends 2 to 4 epochs.
- **Jev was under-briefed.** That run sent Jev bucket keys without their readable names. The question has since been fixed, so Jev's next score is a fairer bar.

The benchmark run that decides the headline is next: full train split, 2 to 3 epochs, against the fixed Jev question.

**Beyond accuracy.** Even where accuracy is close, sys1 offers what Jev cannot:

- **Speed:** about 3 times faster in this run.
- **Calibration:** a temperature fitted on the team's own calibration split, so "how sure" can safely route work.
- **Improvement over time:** it gets better from the team's corrections, while Jev stays fixed.

## How it works

- **Model:** Laya, a ModernBERT-large backbone with a decision head (Apache 2.0), plus a rank-64 LoRA trained with Unsloth's `FastDecisionModel`. One forward pass per decision, no text generation.
- **Training:** a Modal function on an L4 GPU trains on the train split, fits a temperature on the calibration split, saves the adapter to a volume, and scores the new model and untrained Laya on the frozen test split.
- **Serving:** a Modal class loads Laya plus a project's live adapter once, keeps recent ones warm and scales to zero when idle. The FastAPI gateway routes `sys1`, `jev-1.13.0` and `auto` (sys1 when sure, Jev otherwise, and the handoff is flagged for review).
- **App:** a FastAPI server and a React client, with Clerk organizations. Model, trainer, LLM and data-generator integrations sit behind interfaces with fakes, so the product runs and tests without GPUs or API keys.

## Trust, security and ethics

- **Never trained on Jev.** Jev's answers are never used as training labels or to choose what gets labelled, per TypeSafe's customer agreement (section 2.3b). It would also cap sys1 at Jev's quality.
- **Honest comparisons.** Test examples are frozen at the first training and never trained on, calibrated on or used to tune prompts. Jev is pinned to a versioned model id, and its saved answers are reused only for the exact question it was asked.
- **Scoped access.** Every project, model, decision and batch is scoped to one Clerk organization. API keys are hashed at rest and tied to one project. Changing the live model or creating keys is limited to admins.
- **People stay in the loop.** Unsure answers go to a person; a retrained model never replaces the live one without an admin's click.
- **No real customer data.** BANKING77 is public (CC BY 4.0); the synthetic support-ticket set was generated from a written policy.

## Status, risks and what's next

**Status.** The full journey runs end to end and is deployed: the app on Railway, training and inference on Modal, and Jev on TypeSafe's API. Each organization can keep two models and run one training at a time, which keeps GPU spend on an open site bounded.

**Risks and our answers:**

| Risk | Answer |
| --- | --- |
| "Fine-tuning beats zero-shot on BANKING77 is expected." | The product is how a team gets there from zero. Next: a learning curve showing how few examples per intent it takes to pass Jev. |
| Many options favour Jev. | Laya reads all bucket names in a 512-token window, and the model card shows Jev ahead above about 20 options. The full-data run tests whether fine-tuning closes that gap at 77. |
| Cold starts. | The first call after 10 idle minutes waits about a minute. Production would keep one container warm per active customer. |
| GPU cost per customer. | One shared base model; each customer adds only an adapter (about 135 MB), loaded on demand. |
| TypeSafe adds fine-tuning. | system1 is the workflow around the model (rules, data, review, the improve loop), and it can wrap any Jev-compatible model. |

**Roadmap:**

- **Next:** the full BANKING77 benchmark run, then the examples-needed learning curve.
- **V2:** Era by Eon, to test the onboarding agent.
- **V3:** SurrealDB agent memory, so the agent remembers a team's decisions across sessions.
- **Later:** a Claude connector and MCP server, so teams can build and call their models from Claude.
