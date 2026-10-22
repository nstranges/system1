"""Evaluate the hosted Jev model on the typed-decisions test split.

Runs locally (no GPU): each test row is sent to the TypeSafe Jev API and the
answers are scored against the gold labels. Results go to results/jev_*.

    export TYPESAFE_API_KEY=...
    python eval_jev.py --limit 50          # quick smoke test
    python eval_jev.py                     # full test split
"""
import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from datasets import load_dataset

from eval_common import load_test_rows, make_record, report, result_name

API_URL = "https://api.typesafe.ai/v1/systemone"

def load_env(path = ".env"):
    """Export KEY=value lines from .env without overriding variables already set."""
    if os.path.exists(path):
        for line in open(path):
            key, sep, value = line.strip().partition("=")
            if sep and not key.startswith("#"):
                os.environ.setdefault(key.strip(), value.strip())

def build_request(row, model):
    """Turn a dataset row into an API payload."""
    questions = json.loads(row["questions"])
    for q in questions.values():
        # The API takes only `instructions` for noul questions
        if q["type"] == "noul":
            q.pop("criteria", None)
    return {"state": json.loads(row["state"]), "model": model, "questions": questions}

def call_api(payload, api_key, retries = 5):
    """POST one request, backing off on rate limits and server errors."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    for attempt in range(retries):
        resp = requests.post(API_URL, headers = headers, json = payload, timeout = 120)
        if resp.status_code == 429 or resp.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()

def answer_probs(qtype, ans):
    """Return (pred, probability per label) for one API answer."""
    if qtype == "noul":
        p_true = ans["noul"]
        return None, {"true": p_true, "false": 1 - p_true}
    pred = ans["choice"] if qtype == "choice" else None
    return pred, ans["probabilities"]

def evaluate_row(row, api_key, model):
    """Query Jev for one row and score each question against gold."""
    gold = json.loads(row["gold"])
    payload = build_request(row, model)
    response = call_api(payload, api_key)

    records = []
    for name, ans in response["answers"].items():
        qtype = payload["questions"][name]["type"]
        pred, probs = answer_probs(qtype, ans)
        records.append(make_record(row["id"], name, qtype, probs, gold[name]["label"], pred))
    return records, response["model"]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default = "jev-latest")
    parser.add_argument("--limit", type = int, default = None, help = "only evaluate the first N rows")
    parser.add_argument("--workers", type = int, default = 8)
    parser.add_argument("--data", default = "", help = "build_dataset.py parquet; its test split replaces typed-decisions")
    parser.add_argument("--variant", default = "terse", help = "question set for --data: terse or policy")
    args = parser.parse_args()

    load_env()
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise SystemExit("TYPESAFE_API_KEY is not set. Add it to .env or export it.")
    if args.data:
        test = load_test_rows(args.data, args.variant, args.limit or 0)
    else:
        test = load_dataset("LocalLLaMA/typed-decisions", "all", split = "test")
        if args.limit:
            test = test.select(range(min(args.limit, len(test))))
    print(f"Evaluating {args.model} on {len(test)} test rows")

    records, versions, failed = [], set(), 0
    with ThreadPoolExecutor(max_workers = args.workers) as pool:
        futures = [pool.submit(evaluate_row, row, api_key, args.model) for row in test]
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                row_records, version = fut.result()
            except Exception as e:
                failed += 1
                print(f"Row failed: {e}")
                continue
            records.extend(row_records)
            versions.add(version)
            if i % 50 == 0:
                print(f"{i}/{len(test)} rows done")

    records.sort(key = lambda r: (r["id"], r["question"]))
    report(result_name("jev", args.data, args.variant), records, {"version": ",".join(sorted(versions)), "rows": len(test), "failed_rows": failed})

if __name__ == "__main__":
    main()
