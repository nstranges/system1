"""Modal entry points the product server calls. run_project (ModalTrainer) trains a project's LoRA, then scores it
and the untrained base on the project's frozen test examples. Decider (ModalSys1Provider) answers live calls with a
project's trained adapter. Deploy with `make modal-deploy`.

Reuses train.py's steps unchanged. Not exercised without a GPU: smoke-test with a small project first.
"""
import json
import time
from collections import OrderedDict
from pathlib import Path

import modal

from train import app, calibrate_model, data_config, image, model_config, save_adapter, start_training, vol

PROGRESS_DICT = "system1-progress"
pipeline_image = image.add_local_python_source("train")

with pipeline_image.imports():
    from tqdm.auto import tqdm
    from transformers import TrainerCallback
    from unsloth import FastDecisionModel

def predict_rows(model, tokenizer, test_rows):
    """Answer every test row; returns [{id, pred, p_gold, latency_ms}] (the server scores against its own gold)."""
    out = []
    for row in tqdm(test_rows, desc = "Predicting", unit = "row"):
        questions = json.loads(row["questions"])
        name = next(iter(questions))
        gold = json.loads(row["gold"])[name]["label"].lower()
        started = time.perf_counter()
        result = FastDecisionModel.predict(model, tokenizer, row["state"], questions)[name]
        probs = {str(k).lower(): float(v) for k, v in result["probabilities"].items()}
        out.append({
            "id": row["id"],
            "pred": str(result["answer"]),
            "p_gold": probs.get(gold, 0.0),
            "latency_ms": (time.perf_counter() - started) * 1000,
        })
    return out

class LiveProgress(TrainerCallback if "TrainerCallback" in globals() else object):
    """Reports step, epoch and loss to the progress Dict, at most every few seconds, for the product's details view."""

    def __init__(self, push, every = 3.0):
        self.push, self.every, self.last = push, every, 0.0
        self.loss, self.eval_loss = [], []

    def _send(self, state, force = False):
        if not force and time.monotonic() - self.last < self.every:
            return
        self.last = time.monotonic()
        stride = max(1, len(self.loss) // 200)  # keep the payload small on long runs
        self.push({
            "step": state.global_step,
            "total_steps": state.max_steps,
            "epoch": round(state.epoch or 0, 2),
            "history": self.loss[::stride],
            "eval_history": self.eval_loss,
        })

    def on_log(self, args, state, control, logs = None, **kwargs):
        if logs and "loss" in logs:
            self.loss.append([state.global_step, round(float(logs["loss"]), 4)])
        self._send(state)

    def on_evaluate(self, args, state, control, metrics = None, **kwargs):
        if metrics and "eval_loss" in metrics:
            self.eval_loss.append([round(state.epoch or 0, 2), round(float(metrics["eval_loss"]), 4)])
        self._send(state, force = True)

@app.function(image = pipeline_image, gpu = "L4", timeout = 60 * 60 * 2)
def evaluate_base(test_rows):
    """Untrained Laya on the test rows (same load as eval_laya.py)."""
    model, tokenizer = FastDecisionModel.from_pretrained(
        model_name = "convaiinnovations/laya", max_seq_length = 512, load_in_4bit = False
    )
    FastDecisionModel.for_inference(model)
    return predict_rows(model, tokenizer, test_rows)

@app.function(image = pipeline_image, gpu = "L4", timeout = 60 * 60 * 4, volumes = {"/outputs": vol})
def run_project(payload):
    """payload: {project_id, epochs, rows (train + cal), test_rows}. Stages match the server's progress names."""
    call_id = modal.current_function_call_id()
    progress = modal.Dict.from_name(PROGRESS_DICT, create_if_missing = True)

    def stage(name, **detail):
        progress[call_id] = {"stage": name, **detail}

    base_call = evaluate_base.spawn(payload["test_rows"])  # runs on its own GPU while this one trains

    stage("preparing")
    model, tokenizer = model_config()
    train_items, eval_items, cal_items = data_config(tokenizer, model, payload["rows"], "labels")

    stage("learning")
    live = LiveProgress(lambda detail: stage("learning", **detail))
    stats = start_training(model, tokenizer, train_items, eval_items, payload["epochs"], [live])

    stage("checking")
    calibration = calibrate_model(model, tokenizer, cal_items)
    folder = f"/outputs/projects/{payload['project_id']}/{call_id}"
    save_adapter(model, tokenizer, folder)
    vol.commit()

    stage("testing")
    FastDecisionModel.for_inference(model)
    sys1 = predict_rows(model, tokenizer, payload["test_rows"])
    base = base_call.get()
    return {
        "adapter_ref": f"laya-outputs:{folder.removeprefix('/outputs/')}",
        "metrics": json.loads(json.dumps({"train": getattr(stats, "metrics", {}), "calibration": calibration}, default = str)),
        "evaluations": {"sys1": sys1, "base": base},
    }

ADAPTER_PREFIX = "laya-outputs:projects/"
CACHED_ADAPTERS = 3  # each is a full Laya copy (about 1 GB), so a few fit on the L4 next to each other

def adapter_folder(adapter_ref):
    """The volume folder run_project saved this adapter_ref to. Anything else is refused, so a ref can't escape it."""
    if not adapter_ref.startswith(ADAPTER_PREFIX) or ".." in adapter_ref.split("/"):
        raise ValueError(f"not a project adapter: {adapter_ref!r}")
    return Path("/outputs") / adapter_ref.removeprefix("laya-outputs:")

def load_adapter(folder):
    """Laya plus a run's saved LoRA, head and calibration, ready to predict. Mirrors eval_lora.py's loader."""
    from peft import PeftModel, set_peft_model_state_dict
    from safetensors.torch import load_file

    import torch

    model, tokenizer = FastDecisionModel.from_pretrained(
        model_name = "convaiinnovations/laya", max_seq_length = 512, load_in_4bit = False
    )
    adapter_file = folder / "adapter_model.safetensors"
    if adapter_file.exists():
        # save_pretrained layout: a PEFT adapter plus the decision head in joint_head.safetensors
        adapter_config = json.loads((folder / "adapter_config.json").read_text())
        rank, alpha = adapter_config["r"], adapter_config["lora_alpha"]
    else:
        # save_adapter's fallback when the model has no save_pretrained: raw LoRA + head weights in trainable.pt.
        # train.py sets lora_alpha equal to r, so the rank read from the weights gives both.
        trainable = torch.load(str(folder / "trainable.pt"), map_location = "cpu")
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
        peft_model = next(m for m in model.modules() if isinstance(m, PeftModel))
        result = set_peft_model_state_dict(peft_model, load_file(str(adapter_file)))
        if result.unexpected_keys:
            raise RuntimeError(f"{len(result.unexpected_keys)} adapter weights did not match the model")
        # The head's module name depends on the base model, so find the smallest module holding every saved head weight
        head_weights = load_file(str(folder / "joint_head.safetensors"))
        matches = [(len(m.state_dict()), m) for n, m in model.named_modules() if n and set(head_weights) <= set(m.state_dict())]
        if not matches:
            raise RuntimeError("no module in the model has all the weights in joint_head.safetensors")
        min(matches, key = lambda t: t[0])[1].load_state_dict(head_weights, strict = False)
    else:
        result = model.load_state_dict(trainable, strict = False)
        if result.unexpected_keys:
            raise RuntimeError(f"{len(result.unexpected_keys)} saved weights did not match the model")

    calibration_file = folder / "calibration.json"
    if calibration_file.exists():
        model.decision_config.update(json.loads(calibration_file.read_text()))
    FastDecisionModel.for_inference(model)
    return model, tokenizer

# Scales to zero when idle so it costs nothing between demos; the first call after that pays the load (about a minute).
@app.cls(image = pipeline_image, gpu = "L4", volumes = {"/outputs": vol}, scaledown_window = 10 * 60, timeout = 10 * 60)
class Decider:
    @modal.enter()
    def setup(self):
        self.models = OrderedDict()  # adapter_ref -> (model, tokenizer), least recently used first

    def _model(self, adapter_ref):
        if adapter_ref in self.models:
            self.models.move_to_end(adapter_ref)
            return self.models[adapter_ref]
        folder = adapter_folder(adapter_ref)
        if not folder.exists():
            vol.reload()  # trained after this container started
        self.models[adapter_ref] = load_adapter(folder)
        while len(self.models) > CACHED_ADAPTERS:
            self.models.popitem(last = False)
        return self.models[adapter_ref]

    @modal.method()
    def decide(self, adapter_ref, state, questions):
        """One Jev-shaped decision: {"answers": {question: {type, choice, confidence, probabilities}}}."""
        return self._decide(self._model(adapter_ref), state, questions)

    @modal.method()
    def decide_many(self, adapter_ref, states, questions):
        """decide() for each state in order, in one call, so a batch check pays the round trip once."""
        loaded = self._model(adapter_ref)
        return [self._decide(loaded, state, questions) for state in states]

    def _decide(self, loaded, state, questions):
        model, tokenizer = loaded
        answers = FastDecisionModel.predict(model, tokenizer, state, questions)
        return {
            "answers": {
                name: {
                    "type": "choice",
                    "choice": str(result["answer"]),
                    "confidence": None if result.get("confidence") is None else float(result["confidence"]),
                    "probabilities": {str(k): float(v) for k, v in result["probabilities"].items()},
                }
                for name, result in answers.items()
            }
        }
