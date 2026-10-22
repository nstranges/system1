import json
import shutil
from pathlib import Path
import modal

app = modal.App("laya-training")
image = (
    modal.Image.debian_slim(python_version = "3.12")
    .pip_install("unsloth==2026.10.3", "datasets", "transformers", "tqdm")
)
vol = modal.Volume.from_name("laya-outputs", create_if_missing = True)

with image.imports():
    import torch
    from tqdm.auto import tqdm
    from unsloth import FastDecisionModel, DecisionTrainer, is_bfloat16_supported
    from datasets import Dataset, load_dataset
    from transformers import TrainingArguments

# decision_config entries that calibrate() writes
CALIBRATION_KEYS = ["temperature", "temperature_by_options", "head_temperature"]
STAGES = ["Loading model", "Preparing data", "Training", "Calibrating"]

# Init the model type and PEFT
def model_config(base = "convaiinnovations/laya"):
    """Load the base model (a Hugging Face id or a saved folder) and attach LoRA adapters."""
    model, tokenizer = FastDecisionModel.from_pretrained(
        model_name = "unsloth/Qwen3.5-4B",
        max_seq_length = 2048,
        load_in_4bit = True,
    )

    model = FastDecisionModel.get_peft_model(
        model,
        r = 64,
        lora_alpha = 64,
        lora_dropout = 0,
        use_gradient_checkpointing = "unsloth",
        random_state = 3407,
    )

    return model, tokenizer

# loading the dataset only
def data_config(tokenizer, model, rows = None, variant = "terse"):
    """Build decision items and split off disjoint eval and calibration sets.

    rows are records from our triage parquet: train rows train, cal rows calibrate, and a slice
    of train is held out for per-epoch eval. The test split is never touched. Without rows it
    falls back to the public typed-decisions dataset.
    """
    # split_holdout defaults to 10% of decisions, capped at 400, so raise both limits
    no_cap = 10**9
    if rows is None:
        dataset = load_dataset("LocalLLaMA/typed-decisions", "all", split = "train")
        items, report = FastDecisionModel.build_dataset(dataset, tokenizer, model)
        tqdm.write(f"Skipped {report['skipped']} of {report['total']} decisions")

        # 20% held out, then half of that for calibration so it never sees the eval rows
        train_items, holdout_items = FastDecisionModel.split_holdout(
            items, seed = 3407, fraction = 0.2, max_items = no_cap
        )
        eval_items, cal_items = FastDecisionModel.split_holdout(
            holdout_items, seed = 3407, fraction = 0.5, max_items = no_cap
        )
    else:
        def build(split):
            selected = [
                {"id": r["id"], "state": r["state"], "questions": r[f"questions_{variant}"], "gold": r["gold"]}
                for r in rows if r["split"] == split
            ]
            items, report = FastDecisionModel.build_dataset(Dataset.from_list(selected), tokenizer, model)
            tqdm.write(f"{split}: skipped {report['skipped']} of {report['total']} decisions")
            return items

        fit_items, cal_items = build("train"), build("cal")
        train_items, eval_items = FastDecisionModel.split_holdout(
            fit_items, seed = 3407, fraction = 0.1, max_items = no_cap
        )
    tqdm.write(
        f"{len(train_items)} training rows, {len(eval_items)} eval rows, "
        f"{len(cal_items)} calibration rows"
    )

    return train_items, eval_items, cal_items

# Calibrate on the holdout set
def calibrate_model(model, tokenizer, cal_items):
    """Calibrate confidences on the holdout set and return the metrics."""
    metrics = FastDecisionModel.calibrate(model, tokenizer, cal_items)
    tqdm.write(f"Calibration metrics: {metrics}")

    return metrics

# Full training loop
def start_training(model, tokenizer, train_items, eval_items):
    """Train the model and return the trainer stats."""
    trainer = DecisionTrainer(
        model = model,
        processing_class = tokenizer,
        train_dataset = train_items,
        eval_dataset = eval_items,
        args = TrainingArguments(
            per_device_train_batch_size = 16,
            gradient_accumulation_steps = 1, # Use GA to mimic batch size!
            warmup_steps = 10,
            num_train_epochs = 3, # Set this for 1 full training run.
            #max_steps = 240,
            learning_rate = 2e-5,
            lr_scheduler_type = "cosine",
            weight_decay = 0.01,
            bf16 = is_bfloat16_supported(),
            fp16 = not is_bfloat16_supported(),
            eval_strategy = "epoch",
            logging_steps = 1,
            output_dir = "/outputs",
            report_to = "none", # Use TrackIO/WandB etc
            seed = 3407,
            disable_tqdm = False,
        ),
    )
    trainer_stats = trainer.train()

    return trainer_stats

def save_merged(model, tokenizer, out_dir):
    """Fold the LoRA into the base weights and save a standalone 16-bit model."""
    Path(out_dir).mkdir(parents = True, exist_ok = True)
    model.save_pretrained_merged(out_dir, tokenizer, save_method = "merged_16bit")

def save_adapter(model, tokenizer, out_dir):
    """Save the adapter, falling back to raw trainable weights."""
    out = Path(out_dir)
    out.mkdir(parents = True, exist_ok = True)

    if hasattr(model, "save_pretrained"):
        model.save_pretrained(str(out))
    else:
        trainable = {n: p.detach().cpu() for n, p in model.named_parameters() if p.requires_grad}
        torch.save(trainable, out / "trainable.pt")

    tokenizer.save_pretrained(str(out))

    # The fitted temperatures live in decision_config, not in the weights, so save them too
    config = getattr(model, "decision_config", {})
    calibration = {k: config[k] for k in CALIBRATION_KEYS if k in config}
    (out / "calibration.json").write_text(json.dumps(calibration, indent = 2))

@app.function(image = image, gpu = "L4", timeout = 60 * 60 * 4, volumes = {"/outputs": vol})
def train(rows = None, variant = "terse", merge = False, base = "convaiinnovations/laya"):
    """Run all stages on the L4, then save the LoRA adapter to the volume."""
    with tqdm(total = len(STAGES), desc = "Overall", unit = "stage") as overall:
        overall.set_postfix_str(STAGES[0])
        model, tokenizer = model_config(base)
        overall.update(1)

        overall.set_postfix_str(STAGES[1])
        train_items, eval_items, cal_items = data_config(tokenizer, model, rows, variant)
        overall.update(1)

        overall.set_postfix_str(STAGES[2])
        trainer_stats = start_training(model, tokenizer, train_items, eval_items)
        overall.update(1)

        overall.set_postfix_str(STAGES[3])
        cal_metrics = calibrate_model(model, tokenizer, cal_items)
        overall.update(1)

    # Clear the previous run's files so old weights (like a stale trainable.pt) can't come back
    shutil.rmtree("/outputs/lora", ignore_errors = True)
    save_adapter(model, tokenizer, "/outputs/lora")
    if merge:
        shutil.rmtree("/outputs/merged", ignore_errors = True)
        save_merged(model, tokenizer, "/outputs/merged")
    vol.commit()
    tqdm.write(str(trainer_stats))
    tqdm.write(str(cal_metrics))

@app.local_entrypoint()
def main(data: str = "", variant: str = "terse", merge: bool = False, base: str = ""):
    """Run training remotely, then download the LoRA adapter to ./lora.

    --data is a parquet from build_dataset.py; without it, train on typed-decisions.
    --variant picks the question set: terse (label list only) or policy.
    --base starts from a saved full model folder (such as ./merged) instead of Laya.
    --merge also saves the LoRA merged into the base model as a full model in ./merged.
    """
    rows = None
    if data:
        import pandas as pd
        rows = pd.read_parquet(data).to_dict("records")
        print(f"Loaded {len(rows)} rows from {data}")
    base_id = "convaiinnovations/laya"
    if base:
        # The container can't see local disk, so copy the folder to the outputs volume first
        with vol.batch_upload(force = True) as upload:
            upload.put_directory(base, "base")
        base_id = "/outputs/base"
        print(f"Uploaded {base} to the volume as base/")
    train.remote(rows, variant, merge, base_id)

    for folder in ("lora", "merged") if merge else ("lora",):
        download(folder)

def download(folder):
    """Copy a folder of the outputs volume into the working directory."""
    for entry in vol.listdir(folder, recursive = True):
        if entry.type != modal.volume.FileEntryType.FILE:
            continue
        dest = Path(entry.path)
        dest.parent.mkdir(parents = True, exist_ok = True)
        with open(dest, "wb") as f:
            for chunk in vol.read_file(entry.path):
                f.write(chunk)
        print(f"Downloaded {dest}")