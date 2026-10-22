# system1 journey v2: data first

Oct 22, 2026 · Thomas Michalski and Nicholas Stranges · Status: draft for approval

This replaces these sections of the [Oct 21 product design](2026-10-21-system1-product-design.md):
- "Product shape"
- "Recommended journey"
- "Other journeys"
- "Screen designs"
- the stage list in "The onboarding agent"
- the Should and Could rows of "Hackathon cut"

Everything else there still stands: who it's for, the hackathon scoring, the TypeSafe terms, the gateway, the architecture, contracts and modularity, security, the roadmap and the business story. Phase 1 (the benchmark) is unchanged.

## Why

The first build assumed every project starts with written rules. Thomas and Nicholas's review found three problems:

- **Data is the real backbone.** Teams either have history (past decisions), have nothing, or have a little. The product needs a clear path for each.
- **The screens leaked our machinery.** "Facts / options / rules" confused a first-time user. "Use case" was a stage when it should be the start. "Try" came before there was a model to try.
- **The improvement loop needs a "how sure" signal** that a person can act on.

## The journey

**Define → Data → Review → Train → Use ⇄ Improve.** Improve loops back to Train.

The stage rail shows these six steps. Each step has a one-line hint at the top saying what it's for and what to do next.

### 0. New project (replaces the Use case stage)

The dashboard shows a single primary button, **New project**, and the project list. The gallery moves inside the new-project flow.

The new-project dialog asks for a name and one sentence on what's being decided. Then it asks how to start:
- **From scratch:** the assistant helps you.
- **From an example:** the gallery templates, including the trained flagship.
- **From my past decisions:** goes to the Upload flow.
- **From my documents:** upload a policy or guide, and the assistant drafts the buckets.

### 1. Define

What you're deciding, and how. The screen has:
- **Buckets:** the possible outcomes, 2 to 15 of them. Each has a name, a short "use this when…" description and an optional example.
- **Guidelines:** optional plain-English sentences that help decide between buckets, in priority order. For example: "Fraud wins over everything", or "If the amount isn't stated, treat it as small."
- **What comes in:** one to three examples of a real input, such as a ticket, an email or a form row. Generation and upload both use these.
- **Context:** files and pasted text such as policies, SOPs or FAQs. The "Add context" button is always available here, and as a paperclip on the assistant.
- **Draft from my examples / Draft from my documents:** the assistant proposes buckets and guidelines. You edit them and approve.
- **Quick check (optional):** runs two or three made-up inputs through Jev with your buckets and guidelines, so you can see whether the buckets make sense. It is not a test of your model.

Hidden under **Advanced** are the machine-checkable rule conditions (the `when` trees). Only the rule-labelled flagship needs them.

### 2. Data

There are three big choices.

**Upload examples (ingestion):**
1. Choose a CSV, Excel or JSONL file.
2. Preview it.
3. Map the columns: the input (one or several columns, joined) and the decision. Id and date are optional.
4. Map the labels to buckets. Existing values become buckets if Define is empty. The UI suggests merges for near-duplicate values and lets you drop rare ones.
5. Clean it: remove empty rows and exact duplicates, and flag over-long inputs.
6. Save.

**Generate examples (synthetic, simple version):**
- **Inputs:** the buckets, guidelines, context, the "what comes in" samples, and a target per bucket. The default is 30 per bucket, with a cap per run.
- **Steps:**
  1. Write the examples in batched prompts per bucket. Vary length, tone and edge cases, and never name the bucket.
  2. Run a leak check.
  3. De-duplicate.
  4. Run a blind check: Claude labels each example without knowing which bucket it was written for.
- **Label:** the bucket it was written for.
- **How sure:** the probability the blind check gave that bucket.
- **A confirmation card** shows the time and cost before anything runs.

**Both (mix):** upload what you have, then generate only enough to bring each bucket up to target. The uploaded rows are used as style samples.

Every example records its **source** (uploaded, generated or corrected).

**The test set is set aside here and frozen.** The split is stratified 70/10/20 into train, calibration and test.
- In the mix route, the test set comes from uploaded rows wherever there are enough.
- When the test set is synthetic, the UI says plainly that scores on made-up data run higher than real life.

**Minimum to train:** about 30 examples per bucket in total.

### 3. Review

Two panels:
- **Health:** examples per bucket, balance warnings, sources, split sizes with a lock icon on the test set, duplicates removed, and over-long inputs.
- **Sort the least sure:** the generated examples with the lowest "how sure", up to 30, shown as cards you drag (or click) into the right bucket. Agreeing confirms an example, and moving it relabels it. Uploaded rows have no score yet, so they don't appear here.

### 4. Train

- **Train my model** opens a confirmation card, then a job with plain progress stages: preparing, learning, checking, testing.
- **Report card:** your model, Jev with your guidelines, Jev with buckets only, and the untrained base model, all on the frozen test set. Then a verdict and the next step.

**Training is a placeholder until Nicholas's trainer lands.** It goes through the existing `Trainer` contract:
- The default adapter, `PreviewTrainer`, walks through the stages in about 20 seconds.
- It then finishes with status **preview**: no model is produced, and the report card shows only the Jev rows, which are real. Your model's row says "Real training connects soon."
- The flagship (Tallyfern) keeps its recorded results, with the sample-numbers banner while they're fixtures.

Nicholas's Modal trainer and serving replace `PreviewTrainer` and the sys1 provider by configuration later. Nothing pretends to be a trained model.

### 5. Use

- **Try:** type or paste an input, or pick one from your test set. You see your model and Jev side by side, each with a "how sure" bar.
  - Your model answers live once one is connected. Until then the flagship shows its recorded answers, labelled "recorded", and other projects show "connects when training is live".
- **API:** keys, the model picker and snippets. These are unchanged from Phase B.

### 6. Improve

- **Inbox:** live decisions from your model, least sure first, plus anything a person marked ✗. Sorting one into a bucket records a correction.
- **"N new answers since your last training"** with a **Retrain** button. Retrain uses the same placeholder flow as Train until the real trainer exists.
- **Promote only on improvement:** a retrained version goes live only if it beats the current one on the same frozen test set. This applies once real training exists.

## "How sure"

The word in the UI is always "how sure", never "confidence" or "probability". Details sit in a drawer.

| Where | Signal |
|---|---|
| Your model's answers | The margin between the top two calibrated probabilities. Low margin means least sure. Calibration is fitted on the calibration split, and Jev's `confidence` field is never used |
| Generated examples | The blind check's probability for the assigned bucket |
| Uploaded examples | None for now. Later: the model's own disagreement with the label after the first training |

Jev is never used to choose what gets labelled or to label anything (TypeSafe §2.3b).

## The assistant

- **One thread per project,** persistent, with a "Start over" action. It knows the current step, the buckets and guidelines, the context file names, the data health and the "how sure" summary.
- **It acts only through tools:**
  - `show_choices` and `show_fit`
  - `set_buckets` and `set_guidelines`
  - `draft_from_examples` and `draft_from_context`
  - `quick_check`
  - `request_generation` (a confirmation card)
  - `request_training` (a confirmation card)
  - `go_to_stage`
- **Tone:** draft first, then ask. Stage 1 proposes a full first draft of buckets after the first answer rather than interviewing question by question.
- **Model:** `claude-sonnet-5-5`, set by `AGENT_MODEL`.
- **No "bring your own ChatGPT/Claude subscription":** consumer plans give third-party apps no API access. Using your own API key, and the Claude connector, are in the backlog.

## Words on screen

| Internal | On screen |
|---|---|
| options | buckets |
| rules (text) | guidelines |
| inputs / facts | what comes in |
| rule conditions (`when`) | Advanced → conditions |
| probabilities / margin | how sure |
| dataset rows | examples |

Every step and every non-obvious control gets a short hint, through an info icon with a tooltip or a line of helper text.

## Data model changes (server)

- **`Policy` gains `guidelines: list[str]`** for free-text guidance with no specific bucket. Option `covers` holds a bucket's "use this when…" lines. The rules with `when` conditions stay for the flagship, under Advanced. The Jev question builder adds the guidelines to the instructions.
- **New `ContextDoc` table:** id, org_id, project_id, name, kind (`pdf|docx|md|txt|paste`), text (extracted), chars, created_at.
  - **Limits:** 2 MB per file, 10 files per project, and text extraction only (no OCR).
  - **Formats:** PDF via `pypdf`, Word via `python-docx`.
  - **In prompts:** at most 50,000 characters in total.
- **New `Example` table:** id, org_id, project_id, dataset_version, input (text or JSON), label, source (`uploaded|generated|corrected`), split (`train|cal|test`), how_sure (nullable), review (`agree|moved|null`), created_at.
  - The test split is frozen. Later uploads and generations never move existing test rows.
- **New `Job` table** for generation and training progress: kind, status, progress, message, result.
- **Upload limits:** 5 MB and 5,000 rows.
- **The `ExampleGenerator` contract,** `generate(policy, context, samples, targets) -> list[GeneratedExample]`, wraps the simple generator. Thomas's better pipeline replaces it later.
- **The Phase B `feedback`, `decisions` and keys tables are unchanged.**

## What happens to the current build

| Keep as is | Rework | Remove |
|---|---|---|
| Clerk organizations and auth, the projects API, the gateway (`/v1/systemone`, `/v1/feedback`), keys, the Use page, the decision log, feedback and the inbox, the contracts and fakes, the Jev adapter, error handling, the ErrorBoundary | The stage rail (the six new steps), the Rules canvas becomes Define (buckets, guidelines, what comes in, context, Advanced), Try moves into Use, the agent's tools and playbook, the dashboard and new-project dialog, the Improve sorting by "how sure" | The Use case stage (now the new-project dialog), the standalone Try stage, the "Examples / not ready" placeholder |

The rules engine, the question builder and the Tallyfern template stay. The flagship still uses rule conditions.

## Non-goals for the demo

- Real training and serving: Nicholas, later, through the contracts.
- The re-check of uploaded data after training, and generated variants from corrections.
- The first-run onboarding tour, a dataset marketplace or library, and bring-your-own-key.
- OCR, and Google Sheets import.

## Anti-goals (in addition to the Oct 21 list)

- A preview training run that looks like a real trained model.
- Jev labelling or ranking examples.
- Silently reshuffling the test set.

## Data rules after edits (settled from the builder check)

- **The test set freezes at the first training.**
  - Before it, every example's split is assigned when it's written, but labels anywhere, including test rows, can still be fixed in Review.
  - After it, test rows are read-only and never move. Later uploads, generations and corrections go to train or calibration only.
  - The one exception is a bucket with fewer than 6 test rows, such as a newly added bucket. New rows fill its test quota, which bumps `test_set_version`.
- **The report card stores the `test_set_version` it was scored on.** "Promote only on improvement" compares only cards with the same version.
- **`dataset_version` bumps on any change to examples.**
- **Bucket keys never change once examples exist.** Renaming changes the name only.
- **Deleting a bucket that has examples needs an explicit choice:** "drop its examples", or "move them to bucket X". After the freeze, deleting a bucket that has test rows warns that it resets the test set and makes earlier report cards incomparable, and it bumps `test_set_version`.
- **Review sorts train, calibration and test rows before the freeze, and only train and calibration rows after.**
- **Corrections come from `Feedback`, which stays the source of truth for live decisions.**
  - "N new answers since your last training" counts eligible feedback since the last training job of any status, including preview.
  - At retrain, the eligible feedback is copied into `Example` as `source=corrected, split=train`. A correction never lands in test.
- **The inbox never ranks Jev's answers.**
  - It shows decisions from your model, least sure first by margin, plus anything a person marked ✗, ordered by recency.
  - For a project with no model of its own, it shows only the ✗-marked items, with an empty state that says your model's unsure answers will appear here.
- **The flagship's Data and Review are read-only summaries.** "This example was built with our rules-based pipeline: 550 tickets, 13 buckets." Nothing is sorted there, and Train shows its recorded report card as before.
- **The blind check's "how sure" is one structured call per batch.** It returns a probability for each bucket per example, and the UI calls it an estimate.
- **The Jev rows on the report card come from a separate evaluation service, not from the trainer.**
  - They run as part of the Train job, including preview, and are cached per `test_set_version`.
  - Jev calls don't count against the Anthropic token cap.
  - With fewer than 10 test examples per bucket on average, the verdict says "Too few test examples for a firm verdict" instead of naming a winner.
- **The `Trainer` contract gains a `preview` status.** Nicholas's adapter never returns it.

## Calls made by Claude (open to change)

- The step names and order.
- The word "buckets".
- The 70/10/20 split.
- 30 per bucket as both the default target and the minimum.
- A generation cap of 300 examples per run.
- "How sure" as the margin for model answers and the blind-check probability for generated examples.
- `PreviewTrainer` that finishes as "preview" rather than faking metrics.
- `guidelines` as a new Policy field.
- The file-size and row limits.
- `pypdf` and `python-docx` for text extraction.
- Up to 30 cards in the review sort.
