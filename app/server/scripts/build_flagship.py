"""Regenerate the Tallyfern flagship assets under templates/data/tallyfern/.

Run from the repo root with the root venv (pandas and pyarrow live there):
    .venv/bin/python app/server/scripts/build_flagship.py

Writes policy.json, jev_questions.json, samples.jsonl and eval/. Eval files come
from results/triage/ when the real benchmark has written them there, otherwise
they are clearly marked fixtures ("fixture": true) so the UI shows sample numbers.
"""

import json
import random
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "app/server/src/system1/templates/data/tallyfern"
RESULTS = REPO / "results/triage"
BUILD = REPO / "data/build"
SAMPLE_COUNT = 60
# Model key -> results file prefix (the flagship's `eval_models` in gallery.json).
EVAL_PREFIXES = {"sys1": "sys1", "jev_policy": "jev_policy", "jev_labels": "jev_labels", "base": "base"}
# Fixture accuracy per model: made-up, only ever shown under the "Sample numbers" banner.
FIXTURE = {
    "sys1": ("sys1 (sample numbers)", 0.93, 0.85),
    "jev_policy": ("jev-1.13.0 with policy (sample numbers)", 0.78, 0.7),
    "jev_labels": ("jev-1.13.0 labels only (sample numbers)", 0.58, 0.6),
    "base": ("base Laya (sample numbers)", 0.36, 0.5),
}

# Phase 1 modules live at the repo root and read paths relative to it.
sys.path.insert(0, str(REPO))
import os

os.chdir(REPO)
import eval_common
import pandas as pd
import policy as phase1

INPUT_LABELS = {
    "plan_tier": "Plan",
    "region": "Region",
    "seats": "Seats",
    "sso_enabled": "SSO enabled",
    "issue_type": "Main request",
    "secondary_issue": "Secondary issue mentioned",
    "amount_usd": "Amount (USD)",
    "days_since_charge": "Days since charge",
    "api_version": "API version",
}
INPUT_DESCRIPTIONS = {
    "plan_tier": "From the CRM.",
    "region": "From the CRM.",
    "seats": "From the CRM.",
    "sso_enabled": "From the CRM. Only enterprise accounts can enable SSO.",
    "issue_type": "What the customer mainly wants, read from the message.",
    "secondary_issue": "Another issue raised anywhere in the message, if any.",
    "amount_usd": "Stated in the message. Unknown means not met.",
    "days_since_charge": "Stated in the message. Unknown means not met.",
    "api_version": "Stated in the message. Unknown means not met.",
}


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def build_policy() -> dict:
    spec = json.loads((REPO / "data/policy/questions.json").read_text())
    inputs = []
    for key, kind in phase1.FACT_FIELDS.items():
        field = {
            "key": key,
            "label": INPUT_LABELS[key],
            "nullable": key in phase1.NULLABLE,
            "description": INPUT_DESCRIPTIONS[key],
        }
        if isinstance(kind, tuple):
            field |= {"type": "enum", "values": list(kind)}
        else:
            field["type"] = kind
        inputs.append(field)
    options = [
        {"key": key, "name": q["name"], "covers": q["policy"]["covers"], "excludes": q["policy"]["excludes"]}
        for key, q in spec["queues"].items()
    ]
    rules = json.loads((OUT / "rules.json").read_text())
    return {
        "decision_question": "Which Tallyfern support queue should handle this ticket?",
        "question_key": "queue",
        "inputs": inputs,
        "options": options,
        "rules": rules,
    }


def build_samples() -> None:
    final, provisional = BUILD / "triage.parquet", BUILD / "triage_provisional.parquet"
    source = "final" if final.exists() else "provisional"
    df = pd.read_parquet(final if final.exists() else provisional)
    test = df[df["split"] == "test"].sort_values("id")
    by_queue = {q: list(g["id"]) for q, g in test.groupby("queue")}
    # Round-robin over queues so every queue is represented, deterministically.
    rng = random.Random(phase1.SEED)
    for ids in by_queue.values():
        rng.shuffle(ids)
    chosen: list[str] = []
    while len(chosen) < SAMPLE_COUNT and any(by_queue.values()):
        for queue in sorted(by_queue):
            if by_queue[queue] and len(chosen) < SAMPLE_COUNT:
                chosen.append(by_queue[queue].pop())
    rows = test.set_index("id").loc[sorted(chosen)]
    lines = []
    for row_id, r in rows.iterrows():
        lines.append(
            json.dumps(
                {
                    "id": row_id,
                    "split": "test",
                    "state": json.loads(r["state"]),
                    "questions": json.loads(r["questions_terse"]),
                    "gold": {"queue": r["queue"]},
                    "metadata": {"difficulty": r["difficulty"], "rule_id": r["rule_id"], "source": source},
                }
            )
        )
    (OUT / "samples.jsonl").write_text("\n".join(lines) + "\n")
    print(f"samples.jsonl: {len(lines)} rows from the {source} dataset")


def write_fixture(model_key: str, rows: list[dict], queues: list[str]) -> None:
    label, accuracy, confidence = FIXTURE[model_key]
    rng = random.Random(f"{phase1.SEED}-{model_key}")
    records = []
    for row in rows:
        gold = row["gold"]["queue"]
        correct = rng.random() < accuracy
        pred = gold if correct else rng.choice([q for q in queues if q != gold])
        probs = {q: (1 - confidence) / (len(queues) - 1) for q in queues}
        probs[pred] = confidence
        records.append(eval_common.make_record(row["id"], "queue", "choice", probs, gold, pred))
    summary = {
        "model": label,
        "fixture": True,
        "overall": eval_common.summarize(records),
        "per_question": {"queue": eval_common.summarize(records)},
    }
    prefix = EVAL_PREFIXES[model_key]
    (OUT / "eval" / f"{prefix}_predictions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    write_json(OUT / "eval" / f"{prefix}_summary.json", summary)


def build_eval() -> None:
    (OUT / "eval").mkdir(exist_ok=True)
    rows = [json.loads(line) for line in (OUT / "samples.jsonl").read_text().splitlines()]
    for model_key, prefix in EVAL_PREFIXES.items():
        real_predictions = RESULTS / f"{prefix}_predictions.jsonl"
        real_summary = RESULTS / f"{prefix}_summary.json"
        if real_predictions.exists() and real_summary.exists():
            shutil.copy(real_predictions, OUT / "eval" / real_predictions.name)
            summary = json.loads(real_summary.read_text())
            summary.pop("fixture", None)
            write_json(OUT / "eval" / real_summary.name, summary)
            print(f"{model_key}: copied real results")
        else:
            write_fixture(model_key, rows, phase1.QUEUES)
            print(f"{model_key}: wrote fixture results")


def main() -> None:
    write_json(OUT / "policy.json", build_policy())
    write_json(
        OUT / "jev_questions.json",
        {"labels": phase1.load_questions("terse"), "policy": phase1.load_questions("policy")},
    )
    build_samples()
    build_eval()


if __name__ == "__main__":
    main()
