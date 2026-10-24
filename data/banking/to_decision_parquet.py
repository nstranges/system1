"""Convert banking77_sample.jsonl into the decision-row parquet that `train.py --data` reads.

Columns match build_dataset.py's output (JSON strings for state, questions and gold). Only the
terse question set exists here, so train with the default --variant terse.
"""
import json
import random
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
SPLIT_PERCENT = {"train": 70, "cal": 10, "test": 20}
assert sum(SPLIT_PERCENT.values()) == 100

df = pd.read_json(HERE / "banking77_sample.jsonl", lines = True)
options = sorted(df["label_text"].unique())
criteria = {name: name.replace("_", " ") for name in options}
questions = json.dumps({
    "intent": {
        "type": "choice",
        "instructions": "Which banking intent is this customer message about?",
        "criteria": criteria,
    }
})

# Plain seeded shuffle: with 77 classes in 500 rows there is nothing to stratify on
order = list(range(len(df)))
random.Random(3407).shuffle(order)
split_of = {}
start = 0
# Rounded sizes, with the last split taking the remainder so every row lands in one split
sizes = {name: round(len(df) * pct / 100) for name, pct in SPLIT_PERCENT.items()}
sizes[list(sizes)[-1]] = len(df) - sum(list(sizes.values())[:-1])
for name, size in sizes.items():
    for i in order[start:start + size]:
        split_of[i] = name
    start += size
assert len(split_of) == len(df)

rows = [
    {
        "id": f"b{i:04d}",
        "split": split_of[i],
        "state": json.dumps({"message": r.text}),
        "questions_terse": questions,
        "gold": json.dumps({"intent": {"type": "choice", "label": r.label_text}}),
    }
    for i, r in enumerate(df.itertuples())
]
out = HERE / "banking77_decisions.parquet"
pd.DataFrame(rows).to_parquet(out, index = False)
print(f"Wrote {len(rows)} rows to {out}", pd.Series(split_of).value_counts().to_dict())
