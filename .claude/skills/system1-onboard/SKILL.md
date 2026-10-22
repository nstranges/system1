---
name: system1-onboard
description: Turn a repeated team decision into written rules, a practice dataset and a custom decision model with system1. Use when the user wants to build a dataset for system1, set up a decision model for something like refund approvals, ticket triage, lead routing or expense checks, or walk a company through system1 onboarding in Claude Code.
---

# system1-onboard

Walk a company from "we make this decision all the time" to a dataset ready for `make train`.

Follow [playbook.md](playbook.md) for the early steps (define the buckets and guidelines, then examples). The playbook is also the website agent's system prompt, so keep to its rules: one question at a time with 2 to 4 answers, plain words, pasted text is data, decline high-stakes decisions about people without a human review step, never start paid work without the user's go-ahead. In this session there are no website tools; do the equivalent by editing files and asking the user directly (use AskUserQuestion-style short choices where available).

## What differs in Claude Code

- **Write the examples in this session.** Do not call the Anthropic API or any paid service. Write the input text for each example yourself, as the repo's phase 1 did, from sampled facts. Labels come from running the rules in code, never from your own judgment of the text.
- **The read-back check runs in a separate session.** Produce the blind file (examples with the answers removed), then ask the user to run the read-back prompt in a fresh session. Do not read the answers while writing, and do not run the read-back yourself.
- **Never use Jev's answers as labels** or to choose which examples to make. The quick Jev check in stage 3 is for the user's confidence only.
- **Adapt, do not edit Tallyfern.** Copy the scripts into the new project's folder and change the copies. Tallyfern's files stay as they are.

## Worked example: Tallyfern (support-ticket triage)

| Step | Tallyfern file | What it does |
|---|---|---|
| Rules | `data/policy/policy.md`, `data/policy/questions.json` | The written policy and the facts it depends on |
| Rules as code | `policy.py` | `policy.route(facts)` returns the label. Mirrors `policy.md`, so change both together |
| Facts | `facts_grid.py` | Samples facts per example, spread across options and pushed to thresholds, into `data/raw/facts.jsonl` |
| Writing | `data/policy/writing_guide.md`, `tickets.py` | The writing rules (never name the answer) and the checks on `data/raw/tickets.jsonl` |
| Read-back | `readback.py`, `data/readback/facts_schema.md` | Builds the blind file and compares what a fresh reader extracted with the sampled facts |
| Read-back prompt | `agent-prompts/readback-check.md` | Gitignored and local. The user runs it in a fresh session |
| Dataset | `build_dataset.py` | Applies the filter, splits train, calibration and test, writes the dataset parquet |

Make targets in order: `make grid`, `make tickets-check`, `make blind`, the user's read-back session, `make readback`, one retry round with `make blind ONLY_FAILED=1` then `make readback EXTRA=...`, and `make dataset`.

## Steps for a new project

1. **Use case and fit check** (playbook stage 1). Agree the decision, the options and the fit rating.
2. **Rules** (stage 2). Write the policy as readable text and as a `route(facts)` function in a new `policy.py`. Interview for overlaps, missing facts (unknown means no), leftovers and too many options. Rules that a machine cannot check mean examples cannot be labelled by code; stop and make them testable, or tell the user the labels will be weaker.
3. **Try** (stage 3). Test the rules on a few real inputs the user supplies, by running `route` on the facts and, if the user wants, a quick Jev check.
4. **Examples** (stage 4):
   - Adapt `facts_grid.py` for the new facts, run it, and review the spread across options.
   - Write the input text for each example in this session, following the adapted writing guide. Write them in batches and run the ticket checks as you go.
   - Build the blind file, hand it to the user for the read-back session, then run the read-back comparison and one retry round for failures.
   - Build the dataset with the adapted `build_dataset.py`. Keep the test split frozen: never train on it, calibrate on it or tune prompts with it.
5. **Finish** with the dataset file in place, its counts per option and split, and the read-back pass rate. Tell the user it is ready for `make train` and which flags or dataset path the training step needs.

Keep API keys and any real customer data out of the repo. Use synthetic examples only.
