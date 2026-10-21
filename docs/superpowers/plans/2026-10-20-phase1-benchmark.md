# Phase 1 Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 500-ticket synthetic support-triage dataset whose labels come from written rules, train sys1 on it, and benchmark sys1 against Jev (with and without the policy) and base Laya on 150 frozen test tickets.

**Architecture:**
- **Labels come from code, not from the text.** A rules engine (`policy.py`) turns each ticket's facts into a gold queue. A seeded grid (`facts_grid.py`) decides every ticket's facts before Claude writes the ticket text.
- **A blind check filters the tickets.** A separate agent extracts facts from the text alone, and `readback.py` keeps only tickets whose facts route to the same answer.
- **One parquet file feeds training and evaluation.** `build_dataset.py` deduplicates, splits (frozen test set) and writes it. Nicholas's existing train and eval scripts gain a `triage` dataset mode, and `analyze.py` writes the results report.

**Tech Stack:** Python 3.12, Modal (L4), Unsloth `FastDecisionModel` (Laya), `datasets`/`pandas`/`pyarrow`, `requests` (Jev HTTP), `pytest`, `matplotlib`.

**Spec:** [docs/superpowers/specs/2026-10-20-system1-plan-design.md](../specs/2026-10-20-system1-plan-design.md). Reference notes are in [docs/reference/](../../reference/).

## Global Constraints

**Benchmark integrity**
- Jev is pinned to `jev-1.13.0` for every reported run. Log the `model` field from each response.
- The test split is frozen. Nothing is trained, calibrated, prompt-tuned or rewritten using test tickets.
- Gold labels come only from `policy.route(facts)`, never from anyone's judgment.
- Calibration metrics use `probabilities`, never Jev's or Laya's `confidence` field.

**Data**
- At most 15 queues. The plan uses 13.
- The split is 60/10/30 (300/50/150 at 500 tickets), stratified by queue × difficulty. Existing assignments never change when tickets are added.
- Phase 1 uses no Anthropic API. Claude writes the tickets inside an agent session.
- No real customer data. The fictional company's name must not belong to a real company.

**Process**
- Secrets come only from `.env`. Never print, log or commit them.
- Match the repo's Python style:
  - spaces around `=` in keyword arguments and defaults (`seed = 3407`)
  - a one-line docstring on every function
  - sparse comments
- Pure-Python modules get `pytest` tests in `tests/`. Modal scripts are verified with `LIMIT=` smoke runs.
- **Owners:** Thomas (with Claude) owns Tasks 1, 2, 5–9, 11 and 12. Nicholas owns Tasks 3, 4 and 10. Task 13 is optional.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

Each item pairs a likely failure with what should happen instead.

1. **The ticket text gives the answer away** through a paraphrase the keyword check misses, such as "please loop in your finance folks". Expected: these tickets are caught before training. Pinned by the read-back `names_routing` flag (Task 8) and a 20-ticket manual spot check (Task 7, Step 4).
2. **A Jev row fails mid-run**, so the comparison silently uses different tickets per model. Expected: triage runs refuse to report with failed rows, and paired statistics use only shared ids and report `n`. Pinned in Task 10 (`test_triage_run_requires_zero_failures`) and Task 12 (`test_paired_diff_uses_shared_ids`).
3. **The shuffled option order is lost** between the parquet file and the Jev payload. Expected: every model sees the stored order. Pinned in Task 10 (`test_load_rows_preserves_option_order`).
4. **Leakage between splits**, through near-duplicates in different splits or reassigned frozen ids. Expected: no id is in two splits, duplicates are removed before splitting, and test ids never move. Pinned in Task 9 (`test_frozen_assignments_never_change`, `test_dedupe_runs_before_split`).
5. **Laya silently cuts off long tickets, or Unsloth skips rows over the gold format.** Expected: the budget check fails loudly. Pinned in Task 3 (the check exits non-zero) and re-run on the full dataset in Task 9, Step 6.

---

### Task 1: Write the policy, the question text, the facts schema and the writing guide

**Owner:** Thomas with Claude. **Ends with Thomas's review gate.** No tickets get written until he approves.

**Files:**
- Create: `data/policy/policy.md`, `data/policy/questions.json`, `data/readback/facts_schema.md`, `data/policy/writing_guide.md`
- Modify: `Makefile`. Add a `test` target (`$(PYTHON) -m pytest -q`), and add `pytest pandas pyarrow matplotlib` to `install`.
- Test: `tests/test_policy_content.py`

**Interfaces:**
- Produces: `questions.json` in this shape. The order of queues in the file is the canonical queue order.

```json
{
  "instructions": {"terse": "<string>", "policy": {"question": "<string>", "precedence": ["<rule text>", "..."]}},
  "queues": {
    "trust_safety": {"name": "Trust & Safety", "terse": "<= 10 words", "policy": {"covers": ["..."], "excludes": ["..."]}}
  }
}
```

**Draft policy values.** These are pinned here and change only if Thomas changes them at review.
- **Company:** a fictional invoicing and payments platform for small and mid-sized businesses. Pick the name in Step 1.
- **Queues, in canonical order:** `trust_safety`, `incident_response`, `billing_disputes`, `finance_review`, `billing_refunds`, `payments_ops`, `legacy_api`, `api_support`, `enterprise_identity`, `account_access`, `privacy_legal`, `sales`, `general_support`.
- **Priorities:** `P1`, `P2`, `P3`, `P4`.
- **Facts:**

  | Field | Source | Values |
  |---|---|---|
  | `plan_tier` | customer metadata | `free`, `starter`, `pro`, `enterprise` |
  | `region` | customer metadata | `us`, `ca`, `eu`, `uk`, `apac` |
  | `seats` | customer metadata | int, 1–2000 |
  | `sso_enabled` | customer metadata | bool. Only enterprise accounts can have it `true` |
  | `issue_type` | ticket text | `refund_request`, `chargeback_dispute`, `billing_question`, `failed_payout`, `login_problem`, `api_error`, `data_request`, `outage_report`, `security_concern`, `plan_change`, `how_to` |
  | `secondary_issue` | ticket text | same values, or `null` |
  | `amount_usd` | ticket text | number, or `null` |
  | `days_since_charge` | ticket text | int, or `null` |
  | `api_version` | ticket text | `v1`, `v2`, or `null` |

- **Routing rules.** The first match wins. "Mentions X" means `issue_type` or `secondary_issue` equals X.

  | Rule | Condition | Queue |
  |---|---|---|
  | R01 | mentions `security_concern` | `trust_safety` |
  | R02 | mentions `outage_report` | `incident_response` |
  | R03 | mentions `chargeback_dispute` | `billing_disputes` |
  | R04 | `issue_type` is `refund_request` and (`amount_usd` > 500 or `days_since_charge` > 30) | `finance_review` |
  | R05 | `issue_type` is `refund_request` | `billing_refunds` |
  | R06 | `issue_type` is `failed_payout` | `payments_ops` |
  | R07 | `issue_type` is `api_error` and `api_version` is `v1` | `legacy_api` |
  | R08 | `issue_type` is `api_error` | `api_support` |
  | R09 | `issue_type` is `login_problem`, plan is `enterprise` and `sso_enabled` | `enterprise_identity` |
  | R10 | `issue_type` is `login_problem` | `account_access` |
  | R11 | `issue_type` is `data_request` and `region` is `eu` or `uk` | `privacy_legal` |
  | R12 | `issue_type` is `plan_change` and (`seats` ≥ 50 or plan is `enterprise`) | `sales` |
  | R13 | anything else | `general_support` |

  Unknown values never satisfy a condition, so an unknown amount isn't over 500 and an unknown version isn't v1.
- **Priority rules.** The first match wins.

  | Condition | Priority |
  |---|---|
  | R01 | P1 |
  | R02 and plan is `enterprise` | P1 |
  | R02 | P2 |
  | R06 and `amount_usd` ≥ 10000 | P2 |
  | R09 | P2 |
  | R12 or R13 | P4 |
  | anything else | P3 |

- [ ] **Step 1: Pick the company name.** Web-search the candidate name and confirm no real software company uses it. Record it at the top of `policy.md`.

- [ ] **Step 2: Write the failing content test** `tests/test_policy_content.py`:

```python
TERSE_MAX_WORDS = 10   # Task 3 lowers this to 6 if Laya's window is 512 tokens

def load():
    """Read questions.json."""
    return json.loads(Path("data/policy/questions.json").read_text())

QUEUES = ["trust_safety", "incident_response", "billing_disputes", "finance_review", "billing_refunds",
          "payments_ops", "legacy_api", "api_support", "enterprise_identity", "account_access",
          "privacy_legal", "sales", "general_support"]

def test_questions_json_has_canonical_queues_in_order():
    assert list(load()["queues"]) == QUEUES

def test_every_queue_has_terse_and_policy_text():
    for key, entry in load()["queues"].items():
        assert entry["name"] and entry["terse"]
        assert 1 <= len(entry["terse"].split()) <= TERSE_MAX_WORDS
        assert entry["policy"]["covers"] and "excludes" in entry["policy"]

def test_policy_md_defines_every_rule_and_queue():
    text = Path("data/policy/policy.md").read_text()
    for rule in [f"R{i:02d}" for i in range(1, 14)]:
        assert rule in text
    for key in QUEUES:
        assert key in text

def test_facts_schema_documents_every_field():
    text = Path("data/readback/facts_schema.md").read_text()
    for field in ["plan_tier", "region", "seats", "sso_enabled", "issue_type", "secondary_issue",
                  "amount_usd", "days_since_charge", "api_version"]:
        assert f"`{field}`" in text
```

- [ ] **Step 3: Run it to confirm it fails.** Run `make install`, then `.venv/bin/python -m pytest tests/test_policy_content.py -q`. Expected: FAIL with `FileNotFoundError`.

- [ ] **Step 4: Write `data/policy/policy.md`** as an internal triage guide:
  - one section per queue
  - the two rule tables above, as numbered rules
  - one worked example ticket per rule, plus both sides of every threshold ($500, 30 days, $10,000, 50 seats)
  - the "unknown means no" default

- [ ] **Step 5: Write `data/policy/questions.json`.**
  - The `terse` descriptions are plain team descriptions with no thresholds.
  - Each `policy` entry carries that queue's rules as `covers` and `excludes` lists.
  - `instructions.policy.precedence` lists R01–R03 overrides in order.
  - Follow Jev's guidance in `docs/reference/jev-api.md`.

- [ ] **Step 6: Write `data/readback/facts_schema.md`** for a reader who has never seen the policy:
  - each field, its allowed values, and whether it comes from metadata or the text
  - **Conversions:** relative time becomes integer days from `created_at` (e.g. "three weeks ago" = 21). Vague time such as "a while ago" counts as not stated. Amounts are converted to USD numbers.
  - `secondary_issue` is only set for a second distinct problem.
  - **No routing terms** appear anywhere.

- [ ] **Step 7: Write `data/policy/writing_guide.md`:**
  - **Leaks:** never name a queue or team, or quote policy.
  - **Metadata:** plan, region, seats and SSO live in the metadata block. Mention them in the text only if a customer naturally would.
  - **Subject line:** 3–10 words.
  - **Body length:** follows the record's `style.length` bucket.
  - **Time phrasing:** state it relatively. Borderline days (27–33) are stated exactly, e.g. "29 days ago".
  - **`implied_facts: true`:** convey the facts that decide the label indirectly but recoverably, e.g. "our old v1 integration".
  - **`distractor: true`:** add one irrelevant number or date.
  - **`confusable_with`:** make the ticket plausibly read as that queue while the facts still decide the label.
  - **Typos:** only when `style.typos` is true.

- [ ] **Step 8: Run the test to confirm it passes.** Run `.venv/bin/python -m pytest tests/test_policy_content.py -q`. Expected: 4 passed.

- [ ] **Step 9: Thomas reviews** `policy.md` and `questions.json`. Apply his edits, and update the rule tables in this plan if they change.

- [ ] **Step 10: Commit.**

```bash
git add data/policy data/readback/facts_schema.md tests/test_policy_content.py Makefile
git commit -m "Add triage policy, question text, facts schema and writing guide"
```

---

### Task 2: Rules engine (`policy.py`)

**Owner:** Thomas with Claude.

**Files:**
- Create: `policy.py`, `tests/test_policy.py`

**Interfaces:**
- Consumes: `data/policy/questions.json` (Task 1).
- Produces:
  - **Constants:** `QUEUES: list[str]` (canonical order, read from `questions.json`), `PRIORITIES = ["P1", "P2", "P3", "P4"]`, `FACT_FIELDS: dict[str, tuple | str]` (allowed values, or `"int"`, `"float"`, `"bool"`, each nullable for text fields), `REFUND_AMOUNT_LIMIT = 500`, `REFUND_WINDOW_DAYS = 30`, `PAYOUT_P2_AMOUNT = 10000`, `SALES_SEATS = 50`, `SEED = 20261020`, `QUESTIONS_PATH = Path("data/policy/questions.json")`.
  - `class Decision(NamedTuple): queue: str; priority: str; rule_id: str`
  - `validate_facts(facts: dict) -> None`, which raises `ValueError` naming the bad field.
  - `route(facts: dict) -> Decision`, which calls `validate_facts` first.
  - `load_questions(variant: str, order: list[str] | None = None) -> dict`. It returns `{"queue": {"type": "choice", "instructions": ..., "criteria": {...}}}`, with criteria in `order` (canonical if `None`). `variant` is `"terse"` or `"policy"`.

- [ ] **Step 1: Write the failing tests** `tests/test_policy.py`. Use a helper `facts(**overrides)` with defaults `plan_tier="pro", region="us", seats=10, sso_enabled=False, issue_type="how_to"` and every other field `None`. Parametrize `test_route` over `(overrides, (queue, priority, rule_id))`:

```python
({"issue_type": "security_concern"}, ("trust_safety", "P1", "R01")),
({"issue_type": "login_problem", "secondary_issue": "security_concern"}, ("trust_safety", "P1", "R01")),
({"issue_type": "outage_report", "plan_tier": "enterprise", "seats": 300}, ("incident_response", "P1", "R02")),
({"issue_type": "outage_report"}, ("incident_response", "P2", "R02")),
({"issue_type": "refund_request", "secondary_issue": "chargeback_dispute"}, ("billing_disputes", "P3", "R03")),
({"issue_type": "refund_request", "amount_usd": 500, "days_since_charge": 30}, ("billing_refunds", "P3", "R05")),
({"issue_type": "refund_request", "amount_usd": 500.01, "days_since_charge": 3}, ("finance_review", "P3", "R04")),
({"issue_type": "refund_request", "amount_usd": 100, "days_since_charge": 31}, ("finance_review", "P3", "R04")),
({"issue_type": "refund_request"}, ("billing_refunds", "P3", "R05")),
({"issue_type": "failed_payout", "amount_usd": 10000}, ("payments_ops", "P2", "R06")),
({"issue_type": "failed_payout", "amount_usd": 9999}, ("payments_ops", "P3", "R06")),
({"issue_type": "api_error", "api_version": "v1"}, ("legacy_api", "P3", "R07")),
({"issue_type": "api_error", "api_version": "v2"}, ("api_support", "P3", "R08")),
({"issue_type": "api_error"}, ("api_support", "P3", "R08")),
({"issue_type": "login_problem", "plan_tier": "enterprise", "seats": 200, "sso_enabled": True}, ("enterprise_identity", "P2", "R09")),
({"issue_type": "login_problem", "plan_tier": "enterprise", "seats": 200}, ("account_access", "P3", "R10")),
({"issue_type": "data_request", "region": "eu"}, ("privacy_legal", "P3", "R11")),
({"issue_type": "data_request", "region": "us"}, ("general_support", "P4", "R13")),
({"issue_type": "plan_change", "seats": 50}, ("sales", "P4", "R12")),
({"issue_type": "plan_change", "seats": 49}, ("general_support", "P4", "R13")),
({"issue_type": "plan_change", "plan_tier": "enterprise", "seats": 60}, ("sales", "P4", "R12")),
({"issue_type": "billing_question"}, ("general_support", "P4", "R13")),
```

Plus these tests:
- `test_unknown_issue_type_raises` uses `issue_type="bogus"` and expects `ValueError`.
- `test_missing_field_raises` drops `region` and expects `ValueError`.
- `test_sso_requires_enterprise` uses `sso_enabled=True` on `plan_tier="pro"` and expects `ValueError`.
- `test_queues_match_questions_json` checks `policy.QUEUES == list(json.load(...)["queues"])`.
- `test_load_questions_respects_order` checks `list(load_questions("terse", order = list(reversed(QUEUES)))["queue"]["criteria"]) == list(reversed(QUEUES))`.
- `test_policy_variant_carries_rules` checks that `load_questions("policy")["queue"]["criteria"]["finance_review"]` is a dict with a `covers` key.

- [ ] **Step 2: Run the tests to confirm they fail.** Run `.venv/bin/python -m pytest tests/test_policy.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'policy'`.

- [ ] **Step 3: Implement `policy.py`** with the interfaces above. Write `route` as an explicit if-chain in rule order, matching Task 1's tables. It must not be data-driven, so it reads like `policy.md`.

- [ ] **Step 4: Run the tests to confirm they pass.** Run `make test`. Expected: all tests pass.

- [ ] **Step 5: Commit.**

```bash
git add policy.py tests/test_policy.py
git commit -m "Add triage rules engine with boundary tests"
```

---

### Task 3: Laya input-window and gold-format check (`check_budget.py`)

**Owner:** Nicholas. Claude writes the sample rows. **Its result sets the ticket-length caps in Task 5.** It can run as soon as Task 2 lands.

**Files:**
- Create: `check_budget.py` (a Modal app, `laya-budget-check`), `data/policy/budget_samples.jsonl` (3 rows)
- Modify: `Makefile` (a `budget` target), `docs/reference/laya-unsloth.md` (record the result)

**Interfaces:**
- Consumes: `policy.load_questions("terse")`. Rows have the triage parquet columns `id`, `state` (JSON string), `questions_terse` (JSON string) and `gold` (JSON string).
- Produces:
  - **Inputs:** `modal run check_budget.py --path <jsonl|parquet>`.
  - **Printed:** `effective_max_len`, the token count per row, and the max and p95 counts.
  - **Exit code:** non-zero if any row exceeds `0.9 * effective_max_len` or if `build_dataset` skips any row.
  - **Gold format:** `{"queue": {"type": "choice", "label": "<queue>"}}`. If Unsloth skips rows in that format, retry with `{"queue": "<queue>"}`, and record whichever works in `laya-unsloth.md`.

- [ ] **Step 1: Claude writes `budget_samples.jsonl`.** Three worst-case rows:
  - a 200-word body
  - a 150-word body
  - a 60-word body with metadata

  Each row uses the terse question, built with `make_state`'s layout: `{"ticket": {"subject", "body", "created_at"}, "customer": {"plan", "region", "seats", "sso_enabled"}}`.

- [ ] **Step 2: Implement `check_budget.py`.**
  - Load Laya as `train.py` does.
  - Report `effective_max_len`. Use the length of `input_ids` in the items `FastDecisionModel.build_dataset` returns when it's available. Otherwise use `min(tokenizer.model_max_length, config.max_position_embeddings, 2048)`.
  - Report `report["skipped"]`.

- [ ] **Step 3: Run it.** Run `make budget PATH_ARG=data/policy/budget_samples.jsonl`. Expected: it prints `effective_max_len`, the token counts and `skipped: 0`.

- [ ] **Step 4: Record the decision** in `docs/reference/laya-unsloth.md`, under "Input window (measured)".
  - If `effective_max_len >= 1024`: length buckets are short 40–80, medium 80–140 and long 140–200 words, and `TERSE_MAX_WORDS = 10`.
  - If it's 512: length buckets are short 40–70, medium 70–110 and long 110–150 words, and `TERSE_MAX_WORDS = 6`. Shorten the terse text in `questions.json` and re-run Task 1's test.

- [ ] **Step 5: Commit.**

```bash
git add check_budget.py data/policy/budget_samples.jsonl Makefile docs/reference/laya-unsloth.md
git commit -m "Add Laya input-window and gold-format check"
```

---

### Task 4: Generalise `train.py`, and explain the typed-decisions LoRA gap

**Owner:** Nicholas. This runs in parallel with Tasks 1–9. The triage part only needs the parquet file from Task 9.

**Files:**
- Modify: `train.py`, `eval_lora.py` (add `--run-name`, loading `lora/<run>/trainable.pt`), `Makefile` (`train` passes `$(ARGS)`, and `eval-lora` passes `RUN` as `--run-name`), `docs/reference/laya-unsloth.md`

**Interfaces:**
- Produces:
  - **Command:** `modal run train.py --dataset {typed-decisions,triage} --train-size N --seed S --run-name NAME --lr LR --epochs E`. The defaults (`typed-decisions`, 0 meaning all, 3407, `""`, 5e-5, 2) reproduce today's behaviour.
  - **Output:** adapters go to `lora/<run_name>/trainable.pt`, or `lora/trainable.pt` when `run_name` is empty.
  - **Triage mode:**
    - Read `data/build/triage.parquet`, shipped into the image only when the file exists.
    - Rename `questions_terse` to `questions`.
    - Use the `split == "train"` rows, shuffled with `seed` and limited to `train_size` if set.
    - Use the `split == "cal"` rows as both `eval_dataset` and calibration items.

- [ ] **Step 1: Add the parameters** to `main` and `train`, and thread them through `model_config`, `data_config` and `start_training`. Pass `random_state = seed`, `learning_rate = lr` and `num_train_epochs = epochs`.

- [ ] **Step 2: Check that the defaults reproduce today's run.** Run `make train`. Expected: the same row counts as before, and `lora/trainable.pt` is written.

- [ ] **Step 3: Gap diagnostic.**
  - Run `make train ARGS="--lr 2e-4 --run-name td_lr2e-4"`, then `make eval-lora RUN=td_lr2e-4`.
  - Expected: accuracy compared against 0.658, with published fine-tuned Laya at about 0.77.
  - If the gap remains, list `trainable.pt` keys containing `head`, and confirm that the decision-head weights were saved.

- [ ] **Step 4: Record the findings and the chosen default `lr`** for triage runs in `docs/reference/laya-unsloth.md`.

- [ ] **Step 5: Commit.**

```bash
git add train.py eval_lora.py Makefile docs/reference/laya-unsloth.md
git commit -m "Parameterise train.py and record LoRA gap diagnosis"
```

---

### Task 5: Facts grid (`facts_grid.py`)

**Owner:** Thomas with Claude. It needs Tasks 2 and 3.

**Files:**
- Create: `facts_grid.py`, `tests/test_facts_grid.py`, `data/raw/facts.jsonl` (generated)
- Modify: `Makefile` (a `grid` target: `$(PYTHON) facts_grid.py --n 550 --seed 20261020 --out data/raw/facts.jsonl`)

**Interfaces:**
- Consumes: `policy.route`, `policy.QUEUES`, `policy.SEED`, and the thresholds.
- Produces:
  - **Constants:** `LENGTH_BUCKETS: dict[str, tuple[int, int]]`, copied from Task 3's decision. `DIFFICULTY_MIX = {"clear": 0.5, "borderline": 0.3, "tricky": 0.2}`.
  - `build_grid(n: int, seed: int, id_start: int = 1) -> list[dict]`. Ids run `t{id_start:04d}` upward. The CLI also takes `--id-start`. Records look like this:

```json
{"id": "t0001", "created_at": "2026-10-05", "facts": {"plan_tier": "...", "...": "..."},
 "queue": "finance_review", "priority": "P3", "rule_id": "R04",
 "difficulty": "borderline", "confusable_with": "billing_refunds",
 "style": {"tone": "angry", "length": "medium", "typos": true, "implied_facts": false, "distractor": false}}
```

**Grid rules:**
- **Dates:** `created_at` falls between 2026-08-01 and 2026-10-15.
- **Queue balance:** each queue gets `n // 13` records, with the remainder spread over the first queues.
- **Difficulty within each queue:** clear `round(0.5k)`, borderline `round(0.3k)`, and tricky takes the rest.
- **Borderline:**
  - Queues with a threshold use values inside these windows: refund amount 450–550, `days_since_charge` 27–33, payout amount 9000–11000, seats 45–55.
  - Other queues set `confusable_with` to a neighbour: `account_access` ↔ `trust_safety`, `billing_refunds` ↔ `billing_disputes`, `privacy_legal` ↔ `general_support`, `enterprise_identity` ↔ `account_access`.
- **Tricky:**
  - Half have a `secondary_issue`. For the R01–R03 queues, the secondary is the override that decides the label. For every other queue, it's a non-overriding issue (`how_to`, `billing_question` or `plan_change`), so the primary still decides.
  - Half have `implied_facts` set to true.
  - A random 30% also get `distractor`.
- **Seats by plan:** free 1–3, starter 1–10, pro 5–60, enterprise 50–2000.
- **SSO:** `sso_enabled` is only true on enterprise accounts, in about 70% of them.
- **Tone:** drawn evenly from `calm`, `angry`, `terse`, `rambling`.
- **Typos:** 25% of tickets.

- [ ] **Step 1: Write the failing tests** `tests/test_facts_grid.py`:

```python
def test_labels_match_rules():
    for r in build_grid(550, 20261020):
        assert tuple(route(r["facts"])) == (r["queue"], r["priority"], r["rule_id"])

def test_queue_balance():
    counts = Counter(r["queue"] for r in build_grid(550, 20261020))
    assert set(counts) == set(QUEUES) and set(counts.values()) <= {42, 43}

def test_difficulty_mix_per_queue():
    grid = build_grid(550, 20261020)
    for q in QUEUES:
        k = sum(r["queue"] == q for r in grid)
        mix = Counter(r["difficulty"] for r in grid if r["queue"] == q)
        assert mix["clear"] == round(0.5 * k) and mix["borderline"] == round(0.3 * k)
        assert mix["tricky"] == k - mix["clear"] - mix["borderline"]

def test_borderline_numbers_in_window():
    for r in build_grid(550, 20261020):
        f, rule = r["facts"], r["rule_id"]
        if r["difficulty"] != "borderline" or rule not in {"R04", "R05", "R06", "R12"}:
            continue
        assert any([
            rule in {"R04", "R05"} and f["amount_usd"] is not None and 450 <= f["amount_usd"] <= 550,
            rule in {"R04", "R05"} and f["days_since_charge"] is not None and 27 <= f["days_since_charge"] <= 33,
            rule == "R06" and 9000 <= f["amount_usd"] <= 11000,
            rule == "R12" and 45 <= f["seats"] <= 55,
        ]), r["id"]

def test_id_start_offsets_ids():
    assert build_grid(13, 1, id_start = 551)[0]["id"] == "t0551"

def test_sso_only_on_enterprise():
    assert all(r["facts"]["plan_tier"] == "enterprise" for r in build_grid(550, 1) if r["facts"]["sso_enabled"])

def test_deterministic():
    assert build_grid(550, 7) == build_grid(550, 7) and build_grid(550, 7) != build_grid(550, 8)

def test_unique_ids_and_valid_lengths():
    grid = build_grid(550, 20261020)
    assert len({r["id"] for r in grid}) == 550
    assert all(r["style"]["length"] in LENGTH_BUCKETS for r in grid)
```

- [ ] **Step 2: Run the tests to confirm they fail.** Run `.venv/bin/python -m pytest tests/test_facts_grid.py -q`. Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `build_grid` and a CLI** (`--n`, `--seed`, `--out`). For each queue and difficulty, sample the facts that would route there, and assert that `route(facts)` agrees before keeping the record.

- [ ] **Step 4: Run the tests to confirm they pass.** Run `make test`. Expected: all tests pass.

- [ ] **Step 5: Generate the grid.** Run `make grid`. Expected: `data/raw/facts.jsonl` has 550 lines.

- [ ] **Step 6: Commit.**

```bash
git add facts_grid.py tests/test_facts_grid.py data/raw/facts.jsonl Makefile
git commit -m "Add seeded facts grid with rule-derived labels"
```

---

### Task 6: Ticket state and validation (`tickets.py`)

**Owner:** Thomas with Claude.

**Files:**
- Create: `tickets.py`, `tests/test_tickets.py`
- Modify: `Makefile` (a `tickets-check` target: `$(PYTHON) tickets.py validate`)

**Interfaces:**
- Consumes: the records from Task 5, and `questions.json` for queue names.
- Produces:
  - `make_state(record: dict, ticket: dict) -> dict`, which returns `{"ticket": {"subject", "body", "created_at"}, "customer": {"plan", "region", "seats", "sso_enabled"}}`.
  - `validate_tickets(records: list[dict], tickets: list[dict]) -> list[str]`, which returns human-readable errors and an empty list when everything is valid.
  - `load_jsonl(path: str | Path) -> list[dict]`.
  - **Ticket file format:** `data/raw/tickets.jsonl` holds one `{"id", "subject", "body"}` per line.

- [ ] **Step 1: Write the failing tests:**
  - `test_make_state_layout` checks the exact keys, and that `customer.plan` equals `facts.plan_tier`.
  - `test_flags_missing_and_extra_ids`.
  - `test_flags_body_length_outside_bucket`, allowing ±10 words of slack.
  - `test_flags_queue_leak`: a body containing `"Finance Review"`, `"finance_review"` or `"finance review"` produces an error naming the id.
  - `test_flags_bad_subject_length` checks for 3–10 words.
  - `test_clean_ticket_passes` expects `[]`.

- [ ] **Step 2: Run the tests to confirm they fail.** Run `.venv/bin/python -m pytest tests/test_tickets.py -q`. Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `tickets.py`.** The leak check matches queue keys, the keys with underscores replaced by spaces, and the `name` values, all case-insensitively.

- [ ] **Step 4: Run the tests to confirm they pass.** Run `make test`. Expected: all tests pass.

- [ ] **Step 5: Commit.**

```bash
git add tickets.py tests/test_tickets.py Makefile
git commit -m "Add ticket state builder and validator"
```

---

### Task 7: Write the 550 tickets

**Owner:** Claude, in-session. It needs Tasks 5 and 6. Task 8's code can be built alongside it.

**Files:**
- Create: `data/raw/tickets.jsonl`

- [ ] **Step 1: Write the tickets in batches of 50 ids**, in `facts.jsonl` order, following `data/policy/writing_guide.md` and each record's `style`. Append each batch to `tickets.jsonl`.

- [ ] **Step 2: After each batch, run `make tickets-check`** and fix every error before starting the next batch. Expected after the final batch: no errors, and 550 tickets.

- [ ] **Step 3: Self-check for variety.** No two tickets should share an opening sentence, and the tones and customer types should vary within each queue.

- [ ] **Step 4: Thomas spot-checks 20 random tickets** (pick them with `shuf -n 20`). He's looking for paraphrased leaks of the answer and for tickets that don't read like a real customer. Rewrite any that fail.

- [ ] **Step 5: Commit.**

```bash
git add data/raw/tickets.jsonl
git commit -m "Add 550 synthetic support tickets"
```

---

### Task 8: Read-back check (`readback.py`)

**Owner:** Thomas with Claude. Thomas runs the fresh agent.

**Files:**
- Create: `readback.py`, `tests/test_readback.py`, `data/readback/tickets_blind.jsonl` and `data/readback/report.json` (both generated)
- Modify: `Makefile` (a `blind` target with `ONLY_FAILED=1` support, and a `readback` target)

**Interfaces:**
- Consumes: `policy.route`, `tickets.make_state`, `tickets.load_jsonl`, and the agent's output in the format of `agent-prompts/readback-check.md`.
- Produces:
  - `write_blind(records: list[dict], tickets: list[dict], path: Path, only_ids: set[str] | None = None) -> int`. It writes `{"id", "state"}` lines only.
  - `extracted_facts(entry: dict) -> dict`. It maps the agent's entry to `{field: value}`, casting `amount_usd` to float, `days_since_charge` and `seats` to int, and `sso_enabled` to bool. A `basis` of `not_stated` or `conflicting` becomes `None`.
  - `compare(records: list[dict], extracted: dict[str, dict]) -> dict`. It returns `{"total", "ok_ids": [...], "failed": [{"id", "reasons": [...]}], "missing": [...], "unrealistic": [...]}`.
  - **CLI:**
    - `readback.py blind [--only-failed data/readback/report.json]` writes `tickets_blind.jsonl`, or `tickets_blind_retry.jsonl` with `--only-failed`.
    - `readback.py compare <extracted.jsonl> [<retry.jsonl> ...]` lets later files override earlier ones, then writes `report.json` and prints a summary.

**Pass rule:** a ticket passes only if all of these hold:
- `route` on the extracted facts gives the same queue *and* priority as the record.
- `flags.names_routing` is false.
- No field that is non-null in the intended facts has the basis `conflicting`.

Tickets flagged `unrealistic` are listed but don't fail.

- [ ] **Step 1: Write the failing tests:**
  - `test_blind_file_has_only_id_and_state`.
  - `test_exact_extraction_passes`.
  - `test_implied_basis_counts_as_match`.
  - `test_missing_decisive_fact_fails`: the intended `api_version` is `v1`, but the extraction says `not_stated`, so it routes to `api_support` and fails with the reason `"queue legacy_api != api_support"`.
  - `test_names_routing_fails`.
  - `test_conflicting_on_set_field_fails`.
  - `test_missing_ticket_listed`.
  - `test_later_file_overrides_earlier`.

- [ ] **Step 2: Run the tests to confirm they fail.** Run `.venv/bin/python -m pytest tests/test_readback.py -q`. Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `readback.py`** with the interfaces above.

- [ ] **Step 4: Run the tests to confirm they pass.** Run `make test`. Expected: all tests pass.

- [ ] **Step 5: Run the check.** Run `make blind`, then Thomas runs `agent-prompts/readback-check.md` in a fresh session. Copy `extracted.jsonl` back, and run `make readback`. Expected: the printed summary shows totals and the failed ids with reasons.

- [ ] **Step 6: One retry round.**
  - Claude rewrites the failed tickets once, keeping their facts, and runs `make tickets-check`.
  - Then run `make blind ONLY_FAILED=1`. Thomas runs the agent on `tickets_blind_retry.jsonl`.
  - Then run `make readback EXTRA=data/readback/extracted_retry.jsonl`.
  - Expected: at least 500 tickets pass. If fewer pass:
    - Generate a supplement with `facts_grid.py --n <shortfall + 10%> --seed 20261021 --id-start 551 --out data/raw/facts_supplement.jsonl`, and append it to `facts.jsonl`.
    - Write those tickets (Task 7, Steps 1–2), then repeat Step 5 for the new ids only.

- [ ] **Step 7: Commit.**

```bash
git add readback.py tests/test_readback.py data/readback Makefile data/raw/tickets.jsonl
git commit -m "Add blind read-back check and results"
```

---

### Task 9: Build the dataset (`build_dataset.py`)

**Owner:** Thomas with Claude.

**Files:**
- Create: `build_dataset.py`, `tests/test_build_dataset.py`, `data/build/triage.parquet` and `data/build/splits.json` (both generated)
- Modify: `Makefile` (a `dataset` target)

**Interfaces:**
- Consumes: `policy.load_questions`, `policy.QUEUES`, `policy.SEED`, `tickets.make_state`, `tickets.load_jsonl`, and `report.json["ok_ids"]`.
- Produces:
  - `char_ngrams(text: str, n: int = 5) -> set[str]` and `jaccard(a: set, b: set) -> float`.
  - `dedupe(items: list[tuple[str, str]], threshold: float = 0.8) -> tuple[list[str], list[str]]`. It takes `(id, body)` pairs in id order, returns `(kept_ids, dropped_ids)`, and keeps the first of each near-duplicate pair.
  - `assign_splits(strata: dict[str, str], seed: int, frozen: dict[str, str]) -> dict[str, str]`. It takes a map from id to stratum key (`"<queue>|<difficulty>"`) and returns a map from id to `train`, `cal` or `test`.
  - `option_order(row_id: str, seed: int) -> list[str]`: `QUEUES` shuffled by `random.Random(f"{seed}:{row_id}")`.
  - `assemble_row(record: dict, ticket: dict, split: str, order: list[str]) -> dict`.
  - **Parquet columns:** `id`, `split`, `difficulty`, `rule_id`, `queue`, `priority`, `facts`, `state`, `questions_terse`, `questions_policy`, `gold`, `gold_priority`, `option_order`.
    - `facts`, `state`, the two question columns, `gold` and `option_order` are JSON strings.
    - `gold` uses the format confirmed in Task 3.
    - Both question variants use the same `option_order`.

**Split algorithm** (the signature doesn't determine it, so it's fixed here):
- Ids in `frozen` keep their split.
- New ids are sorted by stratum, then shuffled within each stratum with `random.Random(seed)`.
- They're dealt from a single counter that continues across strata, using the repeating 10-slot pattern `["test", "train", "train", "test", "train", "cal", "train", "test", "train", "train"]`.

- [ ] **Step 1: Write the failing tests:**
  - `test_dedupe_drops_near_duplicate`: two bodies differing by one word produce one dropped id. Two unrelated bodies produce no drops.
  - `test_split_sizes_500`: 500 ids across 13×3 strata give exactly 300/50/150.
  - `test_split_is_stratified`: each stratum's test share is within 1 ticket of 30%.
  - `test_frozen_assignments_never_change`: assign 500 ids, then add 100 new ones with `frozen` set to the first result. All 500 original assignments are identical.
  - `test_option_order_deterministic_and_shared`: same id and seed give the same order. In `assemble_row`, both question columns have criteria keys in `option_order`.
  - `test_gold_matches_record_queue`.
  - `test_dedupe_runs_before_split`: `main` called on a fixture with a duplicate pair writes only one of the pair to the parquet.
  - `test_only_readback_ok_ids_included`.

- [ ] **Step 2: Run the tests to confirm they fail.** Run `.venv/bin/python -m pytest tests/test_build_dataset.py -q`. Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `build_dataset.py`.** The CLI defaults read `data/raw` and `data/readback/report.json`, and write `data/build/`. It reads `splits.json` as `frozen` if it exists, and always rewrites it.

- [ ] **Step 4: Run the tests to confirm they pass.** Run `make test`. Expected: all tests pass.

- [ ] **Step 5: Build the dataset.** Run `make dataset`. Expected: it prints the kept and dropped counts, split sizes of about 60/10/30 (300/50/150 if exactly 500 are kept), and per-queue counts of at least 25.

- [ ] **Step 6: Run the budget check on the full dataset.** Run `make budget PATH_ARG=data/build/triage.parquet`. Expected: exit code 0 and `skipped: 0`.

- [ ] **Step 7: Commit.**

```bash
git add build_dataset.py tests/test_build_dataset.py data/build Makefile
git commit -m "Build triage dataset with frozen stratified splits"
```

---

### Task 10: Point the eval scripts at the triage dataset

**Owner:** Nicholas, with Claude doing the `eval_jev.py` part. It needs Task 9 for real runs. The tests use a fixture.

**Files:**
- Modify: `eval_common.py`, `eval_jev.py`, `eval_laya.py`, `eval_lora.py`, `Makefile`
- Test: `tests/test_eval_common.py`

**Interfaces:**
- Produces, in `eval_common.py`:
  - `TRIAGE_PATH = Path("data/build/triage.parquet")`.
  - `load_rows(dataset: str = "typed-decisions", split: str = "test", variant: str = "terse", path: Path = TRIAGE_PATH) -> list[dict]`. Each row is `{"id", "state", "questions", "gold"}` as JSON strings, the same shape typed-decisions rows have today. In triage mode, `questions` comes from `questions_<variant>`.
  - `gold_label(entry) -> str`, which accepts either `{"label": ...}` or a bare string.
  - `make_record(row_id, question, qtype, probs, gold_label, pred = None, **extra)`, which adds `"probs"` (the full distribution) and any `extra` keys to the record.
  - `result_name(model: str, dataset: str, split: str, variant: str, run: str = "") -> str`. It returns `model` unchanged for typed-decisions, so existing file names keep working. Otherwise it joins the non-empty parts with `_`, e.g. `jev_triage_policy_test` or `laya_lora_s3407_triage_terse_test`.
- Produces, in the scripts:
  - Every script takes `--dataset`, `--split` and `--variant`.
  - `eval_lora.py` keeps the `--run-name` added in Task 4, and passes it to `result_name` as `run`.
  - The Modal scripts ship the parquet file only when it exists.
  - **Extra fields per record:**
    - `eval_jev.py` adds `latency_s` (wall time per request) and `input_tokens` (from `usage`).
    - The Laya scripts add `latency_s`, timed around `predict`.
  - **Failure rule:** `eval_jev.py` exits non-zero and writes nothing if `dataset == "triage"` and any row failed.
- Produces, in the `Makefile`:
  - Eval targets accept `DATASET`, `SPLIT`, `VARIANT` and `RUN`.
  - A `benchmark` target runs Jev (terse and policy), base Laya and sys1 on both `cal` and `test`.

- [ ] **Step 1: Write the failing tests** `tests/test_eval_common.py`, using a 6-row parquet fixture written with pandas in `tmp_path`:
  - `test_load_rows_triage_shape`: the keys are `{"id", "state", "questions", "gold"}`, and only the requested split comes back.
  - `test_load_rows_variant_selects_column`: the policy variant's criteria are dicts, and the terse variant's are strings.
  - `test_load_rows_preserves_option_order`: the criteria key order equals that row's `option_order`.
  - `test_gold_label_both_formats`.
  - `test_make_record_keeps_probs_and_extra`.
  - `test_result_name_backward_compatible`: `result_name("jev", "typed-decisions", "test", "terse") == "jev"`.
  - `test_triage_run_requires_zero_failures`: call `eval_jev.finish(records, failed = 1, dataset = "triage")` and expect `SystemExit`. Extract that helper from `main`.

- [ ] **Step 2: Run the tests to confirm they fail.** Run `.venv/bin/python -m pytest tests/test_eval_common.py -q`. Expected: FAIL with `ImportError` (no `load_rows`).

- [ ] **Step 3: Implement the `eval_common.py` changes**, then switch the three scripts from `load_dataset("LocalLLaMA/typed-decisions", ...)` to `load_rows(...)`.

- [ ] **Step 4: Run the tests to confirm they pass.** Run `make test`. Expected: all tests pass.

- [ ] **Step 5: Smoke runs.**
  - Run `make eval-jev DATASET=triage VARIANT=policy SPLIT=cal LIMIT=5` and `make eval-laya DATASET=triage SPLIT=cal LIMIT=5`. Expected: `results/jev_triage_policy_cal_*` and `results/laya_triage_terse_cal_*` are written, and the version shown is `jev-1.13.0`.
  - Then run the old default `make eval-jev LIMIT=5`. Expected: it still writes `results/jev_*`.

- [ ] **Step 6: Commit.**

```bash
git add eval_common.py eval_jev.py eval_laya.py eval_lora.py tests/test_eval_common.py Makefile
git commit -m "Add triage dataset mode to eval scripts"
```

---

### Task 11: Run the benchmark

**Owner:** Thomas (Jev runs) and Nicholas (Modal runs). Never re-run a test-split evaluation after looking at test results and then changing the model or prompts.

**Files:**
- Create: `results/*triage*` (generated)

- [ ] **Step 1: Tune Jev's policy prompt on the calibration split only.**
  - Run `make eval-jev DATASET=triage VARIANT=policy SPLIT=cal`.
  - If one confusion dominates, edit that queue's `policy` text in `questions.json`, run `make dataset` (the splits stay frozen) and repeat the run.
  - At most 2 rounds. Record each round's calibration accuracy for the report.

- [ ] **Step 2: Train sys1.**
  - Run `make train ARGS="--dataset triage --seed S --run-name sS --lr <Task 4 lr> --epochs 4"` for S in 3407, 3408 and 3409.
  - For the learning curve, also run `--train-size 100 --run-name n100` and `--train-size 200 --run-name n200`, both with seed 3407.
  - Expected: `lora/s3407`, `lora/s3408`, `lora/s3409`, `lora/n100` and `lora/n200` exist.

- [ ] **Step 3: Run every model on both splits.** Run `make benchmark`. Expected:
  - **Jev:** `results/jev_triage_{terse,policy}_{cal,test}_*`.
  - **Base Laya:** `results/laya_triage_terse_{cal,test}_*`.
  - **sys1:** `results/laya_lora_{s3407,s3408,s3409,n100,n200}_triage_terse_{cal,test}_*`.
  - **Failures:** every Jev run has 0 failed rows.

- [ ] **Step 4: Commit.**

```bash
git add results data/policy/questions.json data/build
git commit -m "Add phase 1 benchmark predictions"
```

---

### Task 12: Analysis and results report (`analyze.py`)

**Owner:** Thomas with Claude. Load the `dataviz` skill before writing the chart code.

**Files:**
- Create: `analyze.py`, `tests/test_analyze.py`, `docs/results/phase1-benchmark.md` and `docs/results/phase1-learning-curve.png` (both generated)
- Modify: `Makefile` (an `analyze` target: `$(PYTHON) analyze.py --l4-price-per-hour $(L4_PRICE)`, which must refuse to run if `L4_PRICE` is unset)

**Interfaces:**
- Consumes: the prediction files named by Task 10's `result_name`, and `triage.parquet`, joined by `id` to get `difficulty` and `rule_id`.
- Produces:
  - `accuracy(records) -> float`
  - `macro_f1(records, labels: list[str]) -> float`
  - `bootstrap_ci(records, metric, n = 2000, seed = 0) -> tuple[float, float]`
  - `paired_diff_ci(a, b, n = 2000, seed = 0) -> dict`, returning `{"diff", "lo", "hi", "n"}`, paired on ids present in both
  - `fit_temperature(cal_records) -> float`, a grid search over T from 0.25 to 5.0 in steps of 0.05, minimising NLL with `log(probs) / T` as logits
  - `apply_temperature(records, t) -> list[dict]`
  - `ece(records)`, reused from `eval_common`
  - `breakdown(records, meta: dict[str, dict], key: str) -> dict[str, float]`
  - `top_confusions(records, k = 10) -> list[tuple[str, str, int]]`
  - `render_report(summary: dict) -> str`

**The report contains:**
- **Main table:** rows A–D (and E if present), each with accuracy and a 95% CI, macro-F1, raw ECE, ECE after temperature scaling, p50 latency, and cost per 10,000 decisions.
- **Headline:** sys1 minus Jev-with-policy, as a paired diff with a CI. Use the median-accuracy seed for the headline, and also show the mean ± sd across the 3 seeds.
- **Breakdowns:** accuracy per difficulty and per rule.
- **Confusions:** the top confusions.
- **Learning curve:** 100/200/300 training tickets.
- **Jev prompt tuning:** the calibration accuracy for each tuning round.
- **Caveats:** synthetic data from a single author, a 150-ticket test set, and the latency definitions.
- **Cost formulas:**
  - Jev: mean `input_tokens` × $0.042 / 1M × 10,000.
  - sys1: p50 `latency_s` × `l4_price_per_hour` / 3600 × 10,000.

- [ ] **Step 1: Write the failing tests** `tests/test_analyze.py`:
  - `test_accuracy_and_macro_f1_known_values`: a 4-record fixture with hand-computed values.
  - `test_paired_diff_uses_shared_ids`: `a` has ids 1–4, `b` has ids 2–5, so the result has `n == 3`.
  - `test_bootstrap_ci_contains_point_estimate`.
  - `test_temperature_reduces_nll_on_overconfident_fixture`: wrong answers at p = 0.99 give a fitted `t > 1`.
  - `test_breakdown_by_difficulty`.
  - `test_render_report_has_headline_and_caveats`: the output contains `"sys1 − Jev with policy"` and `"Caveats"`.

- [ ] **Step 2: Run the tests to confirm they fail.** Run `.venv/bin/python -m pytest tests/test_analyze.py -q`. Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `analyze.py`** with the interfaces above, plus a CLI that writes the report and the chart.

- [ ] **Step 4: Run the tests to confirm they pass.** Run `make test`. Expected: all tests pass.

- [ ] **Step 5: Generate the report.** Look up the current Modal L4 hourly price, then run `make analyze L4_PRICE=<price>`. Expected: `docs/results/phase1-benchmark.md` and the PNG are written. The headline row shows a diff, a CI and `n = 150`.

- [ ] **Step 6: Apply the decision gate** from the spec (§10). Add a "Decision" section to the report, and update the phase line in `CLAUDE.md`.

- [ ] **Step 7: Commit.**

```bash
git add analyze.py tests/test_analyze.py docs/results Makefile CLAUDE.md
git commit -m "Add phase 1 analysis and benchmark report"
```

---

### Task 13 (optional): Row E, a Claude-with-policy ceiling

**Owner:** Thomas runs a fresh agent. Do this only if time allows after Task 12.

**Files:**
- Create: `agent-prompts/claude-ceiling.md` (gitignored) and `results/claude_triage_policy_test_predictions.jsonl`

- [ ] **Step 1: Write the prompt.**
  - The fresh agent reads `policy.md` and the 150 test rows (`state` only, exported by a `--split test` option added to `readback.py blind`).
  - It outputs `{"id", "pred"}` per row.
  - Convert the predictions to records with one-hot `probs`, and report accuracy only. Calibration doesn't apply.

- [ ] **Step 2: Run it, add row E to the report** with `make analyze`, and commit.
