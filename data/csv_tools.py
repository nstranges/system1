"""Move examples between the decision parquet that train.py reads and the CSV the upload wizard reads.

  python data/csv_tools.py to-csv data/banking/banking77_decisions.parquet banking_upload.csv --top 15
  python data/csv_tools.py to-parquet my_examples.csv my_decisions.parquet --text text --label decision

The upload wizard takes at most 5,000 rows, so to-csv samples evenly per label to fit; --top and
--per-label narrow it further.
"""
import argparse
import json
import random
from pathlib import Path

import pandas as pd

SPLIT_PERCENT = {"train": 70, "cal": 10, "test": 20}  # same as the product's SPLIT
SEED = 3407


def state_text(state):
    """The readable text of a parquet row's state (a JSON string, usually {"message": ...})."""
    try:
        value = json.loads(state)
    except (TypeError, json.JSONDecodeError):
        return str(state)
    if isinstance(value, dict) and len(value) == 1:
        return str(next(iter(value.values())))
    return value if isinstance(value, str) else json.dumps(value)


def to_csv(src, out, top, per_label, text_col, label_col, max_rows = 5000):
    df = pd.read_parquet(src)
    df = pd.DataFrame({
        text_col: df["state"].map(state_text),
        label_col: df["gold"].map(lambda g: next(iter(json.loads(g).values()))["label"]),
    })
    counts = df[label_col].value_counts()
    keep = counts.head(top).index if top else counts.index
    per_label = per_label or max(1, max_rows // len(keep))  # default: as many per label as the upload limit allows
    df = df[df[label_col].isin(keep)]
    df = df.sample(frac = 1, random_state = SEED).groupby(label_col).head(per_label)
    df.to_csv(out, index = False)
    print(f"Wrote {len(df)} rows, {df[label_col].nunique()} labels to {out}")
    print(df[label_col].value_counts().to_string())


def to_parquet(src, out, text_col, label_col, question):
    df = pd.read_csv(src, dtype = str).dropna(subset = [text_col, label_col])
    df[label_col] = df[label_col].str.strip()
    labels = sorted(df[label_col].unique())
    criteria = {label: label.replace("_", " ") for label in labels}
    key = "decision"
    questions = json.dumps({key: {"type": "choice", "instructions": question, "criteria": criteria}})

    # Stratified: split each label's rows 70/10/20 so every label reaches the test split.
    rng = random.Random(SEED)
    split_of = {}
    for label in labels:
        idx = list(df.index[df[label_col] == label])
        rng.shuffle(idx)
        n_test = max(1, round(len(idx) * SPLIT_PERCENT["test"] / 100))
        n_cal = round(len(idx) * SPLIT_PERCENT["cal"] / 100)
        for i, row in enumerate(idx):
            split_of[row] = "test" if i < n_test else "cal" if i < n_test + n_cal else "train"

    rows = [
        {
            "id": f"c{n:05d}",
            "split": split_of[i],
            "state": json.dumps({"message": r[text_col]}),
            "questions_terse": questions,
            "gold": json.dumps({key: {"type": "choice", "label": r[label_col]}}),
        }
        for n, (i, r) in enumerate(df.iterrows())
    ]
    pd.DataFrame(rows).to_parquet(out, index = False)
    print(f"Wrote {len(rows)} rows, {len(labels)} labels to {out}", pd.Series(split_of).value_counts().to_dict())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = __doc__, formatter_class = argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest = "cmd", required = True)

    a = sub.add_parser("to-csv", help = "decision parquet -> upload CSV")
    a.add_argument("src", type = Path)
    a.add_argument("out", type = Path)
    a.add_argument("--top", type = int, default = 0, help = "keep only the N most common labels (0 = all)")
    a.add_argument("--per-label", type = int, default = 0, help = "max rows per label (0 = fit the 5,000-row upload limit)")
    a.add_argument("--text", default = "text")
    a.add_argument("--label", default = "decision")

    b = sub.add_parser("to-parquet", help = "any CSV -> decision parquet for train.py --data")
    b.add_argument("src", type = Path)
    b.add_argument("out", type = Path)
    b.add_argument("--text", default = "text", help = "column holding the input text")
    b.add_argument("--label", default = "decision", help = "column holding the label")
    b.add_argument("--question", default = "Which bucket does this belong in?")

    args = parser.parse_args()
    if args.cmd == "to-csv":
        to_csv(args.src, args.out, args.top, args.per_label, args.text, args.label)
    else:
        to_parquet(args.src, args.out, args.text, args.label, args.question)
