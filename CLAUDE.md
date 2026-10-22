# system1

Build North hackathon entry by Thomas Michalski and Nicholas Stranges. Submission is due 2026-10-25 at 23:59 ET, and Demo Day is 2026-10-29.

## The bet

A small fine-tuned decision model ("sys1") beats Jev, TypeSafe's general decision model, on one team's own decisions. sys1 is a LoRA on Laya, trained with Unsloth on Modal. It should match Jev's latency and cost, and sit behind a Jev-compatible API (`POST /v1/systemone`).

## Hackathon

- **Page:** [build-north.devpost.com](https://build-north.devpost.com/). Hosts include Georgian (an investor), Anthropic, Clerk, Eon and SurrealDB. The judges are two people from Georgian, an AI-engineering lead and a Google startups engineer.
- **Judging:** innovation, real-world impact (a specific user, a clear value-add, a path to production), UI and design, tech and deployment (deployed and serving), and security and ethics.
- **Submission:** a public repo, a live link, a demo video of 4 minutes or less, a write-up, the team, and a disclosure of prior work, templates and AI tools used.
- **Demo Day:** the top 10 are announced on Oct 26 and demo in person in Toronto on Oct 29. At least one of us must attend.

## Current phase: benchmark, with the product built alongside (updated 2026-10-21)

The benchmark still decides the pitch. On 2026-10-21 Thomas decided to start building the product on Thu Oct 22, alongside the benchmark, so the demo is ready whichever way the results go. Phase 1 work comes first every day.

- **Use case:** support-ticket triage.
- **Data:** about 500 synthetic tickets, plus the company policy, written by Claude inside an agent session rather than through the Anthropic API (API-based generation is deferred). Gold labels are computed by applying the written policy rules to each ticket's sampled facts, not from Claude's judgment. No hand-labelling.
- **Split:** 300 train / 50 calibration / 150 test, stratified. The test split is frozen: never trained on, calibrated on, or used to tune prompts. Existing test tickets stay in the test set when more tickets are added.
- **Benchmark rows:**
  - Jev with only the label list
  - Jev with the policy
  - base Laya
  - sys1
- **Product:** a B2B website for the support-ops lead at a 20–200 person SaaS company. It has:
  - an onboarding agent
  - a Jev-compatible gateway
  - sys1 served live
  - Clerk sign-in

  It's specified in [docs/superpowers/specs/2026-10-21-system1-product-design.md](docs/superpowers/specs/2026-10-21-system1-product-design.md). It's built on the `product-design` branch. The model side (datasets, the decision provider, training, evaluation results) sits behind contracts with fakes, so it can change without touching the app. The detailed implementation plan gets written with Thomas before any product code. The build runs in blocks with gates where Thomas checks in.
- **Roadmap after the hackathon product:**
  - V2: Era by Eon, to test the agent
  - V3: SurrealDB Agent Memory, if there's time
  - Future: the Claude connector and MCP server

The phase plan, with phase 1 in detail, is in [docs/superpowers/specs/2026-10-20-system1-plan-design.md](docs/superpowers/specs/2026-10-20-system1-plan-design.md). The step-by-step phase 1 build plan, with tasks, owners and tests, is in [docs/superpowers/plans/2026-10-20-phase1-benchmark.md](docs/superpowers/plans/2026-10-20-phase1-benchmark.md).

## Phase 1 data pipeline

**Steps, in order:**
1. `make grid`
2. `make tickets-check`
3. `make blind`
4. Thomas runs `agent-prompts/readback-check.md` in a fresh session. It writes `data/readback/extracted.jsonl`.
5. `make readback`
6. One retry round: `make blind ONLY_FAILED=1`, then the agent again, then `make readback EXTRA=data/readback/extracted_retry.jsonl`.
7. `make dataset`

**Status (2026-10-21):**
- **Done:** the policy (`data/policy/`), the facts grid (`data/raw/facts.jsonl`), 550 validated tickets (`data/raw/tickets.jsonl`) and the blind file.
- **Pending:** the read-back run.
- **Provisional data:** `data/build/triage_provisional.parquet` holds all 550 tickets without the read-back filter. It's for wiring up Tasks 3, 4 and 10, never for reported results.
- **Progress ledger:** `.superpowers/sdd/2026-10-20-phase1-benchmark/progress.md` (gitignored).

**Source of truth:** labels come from `policy.route(facts)`. `policy.py` mirrors `data/policy/policy.md`, so change both together.

## Working rules

- Plan and docs come before code. Nothing gets implemented until the plan is approved.
- Keep API keys out of the repo. Use env vars: `TYPESAFE_API_KEY` or `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, and Modal's own auth.
- Keep confidential and real customer data out of the repo, as the hackathon rules require.
- Pin Jev to a versioned id (`jev-1.13.0`) for any result we report, and log the `model` field from each response.
- Compute calibration from `probabilities`, not `confidence`, because Jev and Laya define `confidence` differently.
- Never use Jev's answers as training labels, or to choose what gets labelled. TypeSafe's customer agreement (§2.3b) forbids it, and it would cap sys1 at Jev's quality.
- Proposed ownership: Nicholas leads the engine (training, calibration, scoring), and Thomas leads the app, the loop, the endpoint and the video. Coordinate before restructuring `train.py`.
- Disclose on Devpost the Modal/Unsloth experiments from before the build week, any templates used, and the AI tools used (including Claude Code).

## Engineering rules (product build)

These apply to the product code in `app/`. The phase 1 scripts at the repo root keep their current setup.

- **Before changing code:** read the relevant code and docs first, follow existing patterns, and stay in scope, with no speculative cleanup. When a request can be read more than one way and the choice is costly to reverse, ask. Otherwise, state the interpretation you chose.
- **Library behaviour:** when unsure how a library works (Clerk, FastAPI, the Anthropic SDK, Unsloth), check the installed version's source, types or docs rather than relying on memory.
- **Naming:** the code is split into `app/server/` (FastAPI) and `app/client/` (React). Say "client" and "server", never "frontend" and "backend".
- **Toolchain:**
  - Server: `uv` (`uv add`, `uv sync`, `uv run`) with a `pyproject.toml` in `app/server/`, and `ruff check` / `ruff format`.
  - Client: `bun` (`bun add`, `bun run`) with Prettier.
  - Don't substitute pip, npm, yarn or pnpm.
- **Checks:**
  - `make format`, `make check` and `make test`.
  - `make docs` regenerates the OpenAPI schema and the client's types after any API change.
  - `make verify` runs everything before a gate.
  - During work, run the smallest relevant tests. Before calling something done, run the full checks for every part you changed. Agent edits don't trigger format-on-save.
- **Failures:**
  - Never claim a check passed unless it ran in the current work.
  - Fix the cause. Don't delete or skip tests, weaken assertions, or catch broad exceptions.
  - Suppress a lint or type error (`noqa`, `type: ignore`, `eslint-disable`) only for a verified false positive, with a comment explaining why.
  - After three failed attempts at the same failure, stop and report what you tried, the evidence and your leading guess.
- **Comments and docs:** comments explain intent, constraints and trade-offs, not what the code obviously does, and never reference tickets or plan steps. Don't hand-edit generated files. Update living docs when a change makes them wrong.
- **Side effects:**
  - Real calls to Anthropic, TypeSafe or Modal happen only in the tagged smoke test, under its spending cap.
  - Ask before deploying, changing Clerk or Modal settings, or sending anything outside the repo.
- **Git:**
  - Commit freely on `product-design`, never on `main`.
  - Use `type(scope): description` messages: an imperative, lowercase subject of 72 characters or less, with the why in the body.
  - Add no Claude attribution lines.
  - Never force-push, discard uncommitted work or rewrite history without asking.

## Environment and commands

- **Commands:** run `make help` for the list (setup, `check-env`, `jev-check`, `train`, `eval-laya`, `eval-lora`, `eval-jev`). The evals take `LIMIT=50` for smoke tests. Product commands (delegating to `app/Makefile`): `dev` (server and client), `format`, `check`, `docs` (OpenAPI schema and client types), `verify` (check, test, client build). `test` runs the phase 1 tests and then the server tests.
- **Environment:** a local `.venv` created with `uv`. Override the location with `VENV=...`. Training and the Laya evals run remotely on Modal. `eval_jev.py` runs locally.
- **Secrets:** stored in `.env`, which is gitignored. The template is `.env.example`, and `make env` copies it. Never print or commit `.env`.
- **Agent prompts:** prompts for separate agent sessions live in `agent-prompts/`, which is gitignored and local only. `readback-check.md` is the blind read-back check, which Thomas runs in a fresh session.

## Reference

- [docs/backlog.md](docs/backlog.md): the running catalog of maybe items, future ideas, things to check, and ideas we decided against. Add new parked ideas there, with the date, as they come up.
- [docs/reference/jev-api.md](docs/reference/jev-api.md): Jev's request and response format, limits, pricing and known weaknesses.
- [docs/reference/laya-unsloth.md](docs/reference/laya-unsloth.md): Laya facts and limits, the Unsloth decision-training API, the dataset format and the current state of `train.py`.
