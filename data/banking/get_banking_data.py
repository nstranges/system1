import json

from datasets import load_dataset

banking = load_dataset("mteb/banking77", split="train")
sample = banking.shuffle(seed=42)

with open("banking77_sample.jsonl", "w") as f:
    for row in sample:
        f.write(json.dumps(row) + "\n")

print(sample.column_names)
print(sample[0])