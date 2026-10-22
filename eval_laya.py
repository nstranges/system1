import json
import modal

app = modal.App("laya-baseline-eval")
image = (
    modal.Image.debian_slim(python_version = "3.12")
    .pip_install("unsloth==2026.10.3", "datasets", "transformers", "tqdm")
)

with image.imports():
    from tqdm.auto import tqdm
    from unsloth import FastDecisionModel
    from datasets import load_dataset

# Same load as train.py, but with no LoRA adapters attached
def model_config():
    """Load the untrained base model."""
    model, tokenizer = FastDecisionModel.from_pretrained(
        model_name = "convaiinnovations/laya",
        max_seq_length = 512,
        load_in_4bit = False,
    )
    FastDecisionModel.for_inference(model)

    return model, tokenizer

def normalize(qtype, result):
    """Return (pred, probability per label) from a predict() answer."""
    if qtype == "noul":
        return str(result["answer"]).lower(), result["probabilities"]
    return str(result["answer"]), result["probabilities"]

@app.function(image = image.add_local_python_source("eval_common"), gpu = "L4", timeout = 60 * 60 * 2)
def evaluate(limit: int = 0, rows = None):
    """Predict every test row with the untrained Laya model and score it against gold."""
    from eval_common import make_record

    model, tokenizer = model_config()
    if rows is not None:
        test = rows
    else:
        test = load_dataset("LocalLLaMA/typed-decisions", "all", split = "test")
        if limit:
            test = test.select(range(min(limit, len(test))))
    tqdm.write(f"Evaluating laya on {len(test)} test rows")

    records = []
    for row in tqdm(test, desc = "Predicting", unit = "row"):
        questions = json.loads(row["questions"])
        gold = json.loads(row["gold"])
        answers = FastDecisionModel.predict(model, tokenizer, row["state"], questions)

        for name, result in answers.items():
            pred, probs = normalize(questions[name]["type"], result)
            records.append(make_record(row["id"], name, questions[name]["type"], probs, gold[name]["label"], pred))

    return records, len(test)

@app.local_entrypoint()
def main(limit: int = 0, data: str = "", variant: str = "terse"):
    """Run the baseline eval remotely and write results/laya_*."""
    from eval_common import load_test_rows, report, result_name

    rows = load_test_rows(data, variant, limit) if data else None
    records, rows = evaluate.remote(limit, rows)
    records.sort(key = lambda r: (r["id"], r["question"]))
    report(result_name("laya", data, variant), records, {"version": "convaiinnovations/laya (untrained)", "rows": rows})
