import json
from pathlib import Path

from datasets import load_dataset

HERE = Path(__file__).parent

banking = load_dataset("mteb/banking77", split="train")

# The full official train split in its original order, as a CSV
banking.to_csv(HERE / "banking77_train.csv")

sample = banking.shuffle(seed=42)

with open(HERE / "banking77_sample.jsonl", "w") as f:
    for row in sample:
        f.write(json.dumps(row) + "\n")

print(sample.column_names)
print(sample[0])
