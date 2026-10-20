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
    from datasets import load_dataset
    from transformers import TrainingArguments

STAGES = ["Loading model", "Preparing data", "Training", "Calibrating"]

# Init the model type and PEFT
def model_config():
    """Load the base model and attach LoRA adapters."""
    model, tokenizer = FastDecisionModel.from_pretrained(
        model_name = "convaiinnovations/laya",
        max_seq_length = 2048,
        load_in_4bit = False,
    )

    model = FastDecisionModel.get_peft_model(
        model,
        r = 16,
        lora_alpha = 16,
        lora_dropout = 0,
        use_gradient_checkpointing = "unsloth",
        random_state = 3407,
    )

    return model, tokenizer

# loading the dataset only
def data_config(tokenizer, model):
    """Build decision items and split off a holdout set."""
    dataset = load_dataset("LocalLLaMA/typed-decisions", "all", split = "train")
    items, report = FastDecisionModel.build_dataset(dataset, tokenizer, model)
    tqdm.write(f"Skipped {report['skipped']} of {report['total']} decisions")

    train_items, eval_items = FastDecisionModel.split_holdout(items, seed = 3407)
    tqdm.write(f"{len(train_items)} training rows, {len(eval_items)} held out")

    return train_items, eval_items

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
            num_train_epochs = 2, # Set this for 1 full training run.
            #max_steps = 240,
            learning_rate = 5e-5,
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

@app.function(image = image, gpu = "L4", timeout = 60 * 60 * 4, volumes = {"/outputs": vol})
def train():
    """Run all stages on the L4, then save the LoRA adapter to the volume."""
    with tqdm(total = len(STAGES), desc = "Overall", unit = "stage") as overall:
        overall.set_postfix_str(STAGES[0])
        model, tokenizer = model_config()
        overall.update(1)

        overall.set_postfix_str(STAGES[1])
        train_items, eval_items = data_config(tokenizer, model)
        overall.update(1)

        overall.set_postfix_str(STAGES[2])
        trainer_stats = start_training(model, tokenizer, train_items, eval_items)
        overall.update(1)

        overall.set_postfix_str(STAGES[3])
        cal_metrics = calibrate_model(model, tokenizer, eval_items)
        overall.update(1)

    save_adapter(model, tokenizer, "/outputs/lora")
    vol.commit()
    tqdm.write(str(trainer_stats))
    tqdm.write(str(cal_metrics))

@app.local_entrypoint()
def main():
    """Run training remotely, then download the LoRA adapter to ./lora."""
    train.remote()

    for entry in vol.listdir("lora", recursive = True):
        if entry.type != modal.volume.FileEntryType.FILE:
            continue
        dest = Path(entry.path)
        dest.parent.mkdir(parents = True, exist_ok = True)
        with open(dest, "wb") as f:
            for chunk in vol.read_file(entry.path):
                f.write(chunk)
        print(f"Downloaded {dest}")