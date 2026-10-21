"""Scoring and result writing shared by eval_jev.py and eval_laya.py.

Both scripts reduce every answer to the same record, so their outputs match:
    {id, question, type, pred, gold, confidence, p_gold, correct}
"""
import json
import math
from collections import defaultdict
from pathlib import Path

ECE_BINS = 10
RESULTS_DIR = Path("results")

def make_record(row_id, question, qtype, probs, gold_label, pred = None):
    """Build one scored record from label probabilities and the gold label.

    `pred` defaults to the argmax of `probs`.
    """
    probs = {str(k).lower(): float(v) for k, v in probs.items()}
    pred = str(pred).lower() if pred is not None else max(probs, key = probs.get)
    gold_label = str(gold_label).lower()
    return {
        "id": row_id,
        "question": question,
        "type": qtype,
        "pred": pred,
        "gold": gold_label,
        "confidence": max(probs.values()),
        "p_gold": max(probs.get(gold_label, 0.0), 1e-12),
        "correct": pred == gold_label,
    }

def ece(records):
    """Expected calibration error with equal-width confidence bins."""
    bins = defaultdict(list)
    for r in records:
        bins[min(int(r["confidence"] * ECE_BINS), ECE_BINS - 1)].append(r)

    total = len(records)
    return sum(
        len(b) / total * abs(sum(r["correct"] for r in b) / len(b) - sum(r["confidence"] for r in b) / len(b))
        for b in bins.values()
    )

def summarize(records):
    """Accuracy, ECE and NLL on the gold label."""
    n = len(records)
    return {
        "n": n,
        "accuracy": sum(r["correct"] for r in records) / n,
        "ece": ece(records),
        "nll": -sum(math.log(r["p_gold"]) for r in records) / n,
    }

def report(name, records, meta):
    """Print the metrics table and write results/<name>_{predictions.jsonl,summary.json}."""
    by_question = defaultdict(list)
    for r in records:
        by_question[r["question"]].append(r)

    summary = {"model": name, **meta, "overall": summarize(records),
               "per_question": {q: summarize(recs) for q, recs in sorted(by_question.items())}}

    RESULTS_DIR.mkdir(exist_ok = True)
    with open(RESULTS_DIR / f"{name}_predictions.jsonl", "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    (RESULTS_DIR / f"{name}_summary.json").write_text(json.dumps(summary, indent = 2))

    print(f"\n{name}  " + "  ".join(f"{k}: {v}" for k, v in meta.items()))
    print(f"{'question':<16}{'n':>6}{'acc':>8}{'ece':>8}{'nll':>8}")
    for q, s in [*summary["per_question"].items(), ("OVERALL", summary["overall"])]:
        print(f"{q:<16}{s['n']:>6}{s['accuracy']:>8.3f}{s['ece']:>8.3f}{s['nll']:>8.3f}")
    print(f"Wrote results/{name}_predictions.jsonl and results/{name}_summary.json")
