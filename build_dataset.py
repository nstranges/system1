"""Build the triage dataset: keep read-back-verified tickets, drop near-duplicates, assign frozen
stratified splits, and write one parquet row per ticket in the Jev/Unsloth format.

    python build_dataset.py                 # -> data/build/triage.parquet + data/build/splits.json
    python build_dataset.py --provisional   # skip the read-back filter -> data/build/triage_provisional.parquet

Provisional builds never write splits.json, so the real build assigns the frozen splits after the read-back.
"""
import argparse
import json
import random
from collections import Counter
from pathlib import Path

import pandas as pd

from policy import QUEUES, SEED, load_questions, route
from tickets import FACTS_PATH, TICKETS_PATH, load_jsonl, make_state

BUILD_DIR = Path("data/build")
READBACK_REPORT = Path("data/readback/report.json")
DUPLICATE_THRESHOLD = 0.8
# Repeating deal order: 6 train, 1 cal, 3 test per 10 tickets
SPLIT_PATTERN = ["test", "train", "train", "test", "train", "cal", "train", "test", "train", "train"]
COLUMNS = ["id", "split", "difficulty", "rule_id", "queue", "priority", "facts", "state",
           "questions_terse", "questions_policy", "gold", "gold_priority", "option_order"]

def char_ngrams(text, n = 5):
    """Lowercased character n-grams of whitespace-normalised text."""
    text = " ".join(text.lower().split())
    return {text[i:i + n] for i in range(max(len(text) - n + 1, 1))}

def jaccard(a, b):
    """Jaccard similarity of two sets."""
    return len(a & b) / len(a | b) if a or b else 1.0

def dedupe(items, threshold = DUPLICATE_THRESHOLD):
    """Given (id, body) pairs in id order, keep the first of each near-duplicate pair."""
    kept, dropped, grams = [], [], []
    for tid, body in items:
        g = char_ngrams(body)
        if any(jaccard(g, other) >= threshold for other in grams):
            dropped.append(tid)
            continue
        kept.append(tid)
        grams.append(g)
    return kept, dropped

def assign_splits(strata, seed, frozen):
    """Map id -> train/cal/test. Frozen ids keep their split; new ids are dealt per stratum."""
    splits = {tid: frozen[tid] for tid in strata if tid in frozen}
    rng = random.Random(seed)
    counter = 0
    for key in sorted(set(strata.values())):
        ids = sorted(tid for tid, s in strata.items() if s == key and tid not in frozen)
        rng.shuffle(ids)
        for tid in ids:
            splits[tid] = SPLIT_PATTERN[counter % len(SPLIT_PATTERN)]
            counter += 1
    return splits

def option_order(row_id, seed):
    """QUEUES shuffled deterministically for one ticket."""
    order = list(QUEUES)
    random.Random(f"{seed}:{row_id}").shuffle(order)
    return order

def assemble_row(record, ticket, split, order):
    """One parquet row; gold comes from the rules, not from any stored label."""
    decision = route(record["facts"])
    return {
        "id": record["id"],
        "split": split,
        "difficulty": record["difficulty"],
        "rule_id": decision.rule_id,
        "queue": decision.queue,
        "priority": decision.priority,
        "facts": json.dumps(record["facts"]),
        "state": json.dumps(make_state(record, ticket)),
        "questions_terse": json.dumps(load_questions("terse", order = order)),
        "questions_policy": json.dumps(load_questions("policy", order = order)),
        "gold": json.dumps({"queue": {"type": "choice", "label": decision.queue}}),
        "gold_priority": decision.priority,
        "option_order": json.dumps(order),
    }

def main(argv = None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--facts", default = str(FACTS_PATH))
    parser.add_argument("--tickets", default = str(TICKETS_PATH))
    parser.add_argument("--readback-report", default = str(READBACK_REPORT))
    parser.add_argument("--out-dir", default = str(BUILD_DIR))
    parser.add_argument("--seed", type = int, default = SEED)
    parser.add_argument("--provisional", action = "store_true",
                        help = "skip the read-back filter; never use for reported results")
    args = parser.parse_args(argv)

    records = {r["id"]: r for r in load_jsonl(args.facts)}
    tickets = {t["id"]: t for t in load_jsonl(args.tickets)}
    ids = sorted(set(records) & set(tickets))
    if not args.provisional:
        ok = set(json.loads(Path(args.readback_report).read_text())["ok_ids"])
        ids = [i for i in ids if i in ok]

    kept, dropped = dedupe([(i, tickets[i]["body"]) for i in ids])
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents = True, exist_ok = True)
    splits_path = out_dir / "splits.json"
    frozen = {} if args.provisional or not splits_path.exists() else json.loads(splits_path.read_text())
    strata = {i: f"{route(records[i]['facts']).queue}|{records[i]['difficulty']}" for i in kept}
    splits = assign_splits(strata, args.seed, frozen)

    rows = [assemble_row(records[i], tickets[i], splits[i], option_order(i, args.seed)) for i in kept]
    df = pd.DataFrame(rows, columns = COLUMNS)
    out = out_dir / ("triage_provisional.parquet" if args.provisional else "triage.parquet")
    df.to_parquet(out, index = False)
    if not args.provisional:
        splits_path.write_text(json.dumps({**frozen, **splits}, indent = 0, sort_keys = True))

    print(f"Kept {len(kept)} of {len(ids)} tickets ({len(dropped)} near-duplicates dropped: {dropped})")
    print(f"Splits: {dict(Counter(splits.values()))}")
    print(f"Smallest queue: {min(Counter(df['queue']).values())} tickets")
    print(f"Wrote {out}" + ("" if args.provisional else f" and {splits_path}"))

if __name__ == "__main__":
    main()
