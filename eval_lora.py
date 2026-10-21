import json
from pathlib import Path
import modal

app = modal.App("laya-lora-eval")
image = (
    modal.Image.debian_slim(python_version = "3.12")
    .pip_install("unsloth==2026.10.3", "datasets", "transformers", "tqdm")
    .add_local_python_source("eval_common")
    .add_local_dir("lora", "/lora")
)

with image.imports():
    import torch
    from tqdm.auto import tqdm
    from unsloth import FastDecisionModel
    from datasets import load_dataset

# Rebuild the train.py model (same LoRA settings) so the saved weights line up by name
def model_config():
    """Load Laya, attach LoRA adapters, then restore the trained weights."""
    model, tokenizer = FastDecisionModel.from_pretrained(
        model_name = "convaiinnovations/laya",
        max_seq_length = 512,
        load_in_4bit = False,
    )

    # Read the LoRA rank from the saved weights so any checkpoint loads (alpha = r, as in train.py)
    trainable = torch.load("/lora/trainable.pt", map_location = "cpu")
    rank = next(v.shape[0] for k, v in trainable.items() if "lora_A" in k)

    model = FastDecisionModel.get_peft_model(
        model,
        r = rank,
        lora_alpha = rank,
        lora_dropout = 0,
        use_gradient_checkpointing = "unsloth",
        random_state = 3407,
    )

    # train.py saved raw trainable weights (LoRA + decision head) to lora/trainable.pt
    result = model.load_state_dict(trainable, strict = False)
    unexpected = set(result.unexpected_keys)
    if unexpected:
        raise RuntimeError(f"{len(unexpected)} saved weights did not match the model, e.g. {sorted(unexpected)[:3]}")
    tqdm.write(f"Restored {len(trainable)} trained tensors (LoRA rank {rank}) from lora/trainable.pt")

    # calibrate() stores its temperatures in decision_config, which trainable.pt doesn't hold
    calibration_file = Path("/lora/calibration.json")
    if calibration_file.exists():
        model.decision_config.update(json.loads(calibration_file.read_text()))
        tqdm.write(f"Applied calibration: {json.loads(calibration_file.read_text())}")
    else:
        tqdm.write("WARNING: lora/calibration.json not found, evaluating uncalibrated (temperature 1.0)")

    FastDecisionModel.for_inference(model)

    return model, tokenizer

def normalize(qtype, result):
    """Return (pred, probability per label) from a predict() answer."""
    if qtype == "noul":
        return str(result["answer"]).lower(), result["probabilities"]
    return str(result["answer"]), result["probabilities"]

@app.function(image = image, gpu = "L4", timeout = 60 * 60 * 2)
def evaluate(limit: int = 0):
    """Predict every test row with the trained LoRA model and score it against gold."""
    from eval_common import make_record

    model, tokenizer = model_config()
    test = load_dataset("LocalLLaMA/typed-decisions", "all", split = "test")
    if limit:
        test = test.select(range(min(limit, len(test))))
    tqdm.write(f"Evaluating laya-lora on {len(test)} test rows")

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
def main(limit: int = 0):
    """Run the LoRA eval remotely and write results/laya_lora_*."""
    from eval_common import report

    records, rows = evaluate.remote(limit)
    records.sort(key = lambda r: (r["id"], r["question"]))
    report("laya_lora", records, {"version": "convaiinnovations/laya + lora/trainable.pt", "rows": rows})
