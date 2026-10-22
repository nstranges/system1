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
vol = modal.Volume.from_name("laya-outputs", create_if_missing = True)

with image.imports():
    import torch
    from tqdm.auto import tqdm
    from unsloth import FastDecisionModel
    from datasets import load_dataset

def restore_adapter_and_head(model, adapter_file):
    """Load adapter_model.safetensors into the PEFT model and joint_head.safetensors into the head."""
    from peft import PeftModel, set_peft_model_state_dict
    from safetensors.torch import load_file

    peft_model = next(m for m in model.modules() if isinstance(m, PeftModel))
    result = set_peft_model_state_dict(peft_model, load_file(str(adapter_file)))
    if result.unexpected_keys:
        raise RuntimeError(f"{len(result.unexpected_keys)} adapter weights did not match the model, e.g. {result.unexpected_keys[:3]}")
    # LoRA B starts at zero, so all-zero B matrices mean the adapter never loaded
    lora_b = [p for n, p in peft_model.named_parameters() if "lora_B" in n]
    if not any(p.abs().sum() > 0 for p in lora_b):
        raise RuntimeError("adapter loaded but every LoRA B matrix is still zero")
    tqdm.write(f"Restored the LoRA adapter ({len(lora_b)} layers) from {adapter_file.name}")

    # The head's module name depends on the base model, so find it by its saved weight names
    head_weights = load_file("/lora/joint_head.safetensors")
    wanted = set(head_weights)
    matches = [(len(m.state_dict()), n, m) for n, m in model.named_modules() if n and wanted <= set(m.state_dict())]
    if not matches:
        raise RuntimeError("no module in the model has all the weights in joint_head.safetensors")
    _, name, module = min(matches, key = lambda t: t[0])  # the smallest module that holds every head weight
    module.load_state_dict(head_weights, strict = False)
    tqdm.write(f"Restored {len(head_weights)} head tensors into '{name}' from joint_head.safetensors")

# Rebuild the train.py model (same LoRA settings) so the saved weights line up by name
def model_config(base = "convaiinnovations/laya", max_seq_length = 512, load_in_4bit = False):
    """Load the base model (Laya or a saved folder), attach LoRA adapters, then restore the trained weights."""
    model, tokenizer = FastDecisionModel.from_pretrained(
        model_name = base,
        max_seq_length = max_seq_length,
        load_in_4bit = load_in_4bit,
    )

    adapter_file = Path("/lora/adapter_model.safetensors")
    if adapter_file.exists():
        # save_pretrained layout: a PEFT adapter plus the decision head in joint_head.safetensors
        adapter_config = json.loads(Path("/lora/adapter_config.json").read_text())
        rank, alpha = adapter_config["r"], adapter_config["lora_alpha"]
    else:
        # Older runs saved raw trainable weights (LoRA + head) to lora/trainable.pt; read the rank from them
        trainable = torch.load("/lora/trainable.pt", map_location = "cpu")
        rank = alpha = next(v.shape[0] for k, v in trainable.items() if "lora_A" in k)

    model = FastDecisionModel.get_peft_model(
        model,
        r = rank,
        lora_alpha = alpha,
        lora_dropout = 0,
        use_gradient_checkpointing = "unsloth",
        random_state = 3407,
    )

    if adapter_file.exists():
        restore_adapter_and_head(model, adapter_file)
    else:
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

@app.function(image = image, gpu = "L4", timeout = 60 * 60 * 2, volumes = {"/outputs": vol})
def evaluate(limit: int = 0, rows = None, base = "convaiinnovations/laya", max_seq_length = 512, load_in_4bit = False):
    """Predict every test row with the trained LoRA model and score it against gold."""
    from eval_common import make_record

    model, tokenizer = model_config(base, max_seq_length, load_in_4bit)
    if rows is not None:
        test = rows
    else:
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
def main(limit: int = 0, data: str = "", variant: str = "terse", base: str = "", model: str = "",
         max_seq_length: int = 512, load_in_4bit: bool = False):
    """Run the LoRA eval remotely and write results/laya_lora_*.

    --base is the full model folder the LoRA was trained from (as in train.py --base).
    --model is a Hugging Face id for a different base, such as unsloth/Qwen3.5-4B, and must match
    the model, --max-seq-length and --load-in-4bit the LoRA in ./lora was trained with.
    """
    from eval_common import load_test_rows, report, result_name

    rows = load_test_rows(data, variant, limit) if data else None
    base_id = model or "convaiinnovations/laya"
    if base:
        with vol.batch_upload(force = True) as upload:
            upload.put_directory(base, "base")
        base_id = "/outputs/base"
    records, rows = evaluate.remote(limit, rows, base_id, max_seq_length, load_in_4bit)
    records.sort(key = lambda r: (r["id"], r["question"]))
    name = f"lora_{model.split('/')[-1].lower()}" if model else "laya_lora"
    report(result_name(name, data, variant), records, {"version": f"{base or base_id} + lora", "rows": rows})
