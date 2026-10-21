# system1

Build North hackathon entry by Thomas Michalski and Nicholas Stranges. Submission is due 2026-10-25 at 23:59 ET, and Demo Day is 2026-10-29.

## The bet

A small fine-tuned decision model ("sys1") beats Jev, TypeSafe's general decision model, on one team's own decisions. sys1 is a LoRA on Laya, trained with Unsloth on Modal. It should match Jev's latency and cost, and sit behind a Jev-compatible API (`POST /v1/systemone`).

## Current phase: benchmark (decided 2026-10-20)

Prove or disprove the bet before building any product.

- **Use case:** support-ticket triage.
- **Data:** about 500 synthetic tickets, plus the company policy, written by Claude inside an agent session rather than through the Anthropic API (API-based generation is deferred). Gold labels are computed by applying the written policy rules to each ticket's sampled facts, not from Claude's judgment. No hand-labelling.
- **Split:** 300 train / 50 calibration / 150 test, stratified. The test split is frozen: never trained on, calibrated on, or used to tune prompts. Existing test tickets stay in the test set when more tickets are added.
- **Benchmark rows:**
  - Jev with only the label list
  - Jev with the policy
  - base Laya
  - sys1
- **Deferred until results are in:** the confidence-based review queue, the retraining loop, user-built datasets, the web app and MCP.

The full plan, covering phase 1 in detail and later phases in outline, is in [docs/superpowers/specs/2026-10-20-system1-plan-design.md](docs/superpowers/specs/2026-10-20-system1-plan-design.md).

## Working rules

- Plan and docs come before code. Nothing gets implemented until the plan is approved.
- Keep API keys out of the repo. Use env vars: `TYPESAFE_API_KEY` or `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, and Modal's own auth.
- Keep confidential and real customer data out of the repo, as the hackathon rules require.
- Pin Jev to a versioned id (`jev-1.13.0`) for any result we report, and log the `model` field from each response.
- Compute calibration from `probabilities`, not `confidence`, because Jev and Laya define `confidence` differently.
- Proposed ownership: Nicholas leads the engine (training, calibration, scoring), and Thomas leads the app, the loop, the endpoint and the video. Coordinate before restructuring `train.py`.
- Disclose on Devpost the Modal/Unsloth experiments from before the build week and any templates used.

## Environment

- Local `.venv` (Python 3.12) with `modal` installed. Training runs remotely on Modal: `modal run train.py`.

## Reference

- [docs/reference/jev-api.md](docs/reference/jev-api.md): Jev's request and response format, limits, pricing and known weaknesses.
- [docs/reference/laya-unsloth.md](docs/reference/laya-unsloth.md): Laya facts and limits, the Unsloth decision-training API, the dataset format and the current state of `train.py`.
