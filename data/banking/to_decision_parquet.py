"""Convert the full BANKING77 (mteb/banking77) into the decision-row parquet that `train.py --data` reads.

The official test half is the test split. A seeded CAL_PERCENT slice of the train half becomes cal.

Columns match build_dataset.py's output (JSON strings for state, questions and gold). Only the
terse question set exists here, so train with the default --variant terse.
"""
import json
import random
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
CAL_PERCENT = 10

from datasets import load_dataset

banking = load_dataset("mteb/banking77")
train_df, test_df = banking["train"].to_pandas(), banking["test"].to_pandas()
df = pd.concat([train_df, test_df], ignore_index = True)
options = sorted(df["label_text"].unique())
criteria = {name: name.replace("_", " ") for name in options}
questions = json.dumps({
    "intent": {
        "type": "choice",
        "instructions": "Which banking intent is this customer message about?",
        "criteria": criteria,
    }
})

# Plain seeded shuffle of the train half: with 77 classes there is little to stratify on
n_train = len(train_df)
order = list(range(n_train))
random.Random(3407).shuffle(order)
n_cal = round(n_train * CAL_PERCENT / 100)
split_of = {i: "test" for i in range(n_train, len(df))}
for rank, i in enumerate(order):
    split_of[i] = "cal" if rank < n_cal else "train"
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
